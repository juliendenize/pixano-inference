# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from pathlib import Path

import pyarrow as pa
import shortuuid
import tensorflow as tf
import tensorflow_hub as hub
from PIL import Image
from pixano.core import arrow_types
from pixano.models import InferenceModel
from pixano.transforms import coco_names_91, xyxy_to_xywh


class EfficientDet(InferenceModel):
    """TensorFlow Hub EfficientDet Model

    Attributes:
        name (str): Model name
        id (str): Model ID
        device (str): Model GPU or CPU device
        source (str): Model source
        info (str): Additional model info
        model (tf.keras.Model): TensorFlow model
    """

    def __init__(self, id: str = "", device: str = "/GPU:0") -> None:
        """Initialize model

        Args:
            id (str, optional): Previously used ID, generate new ID if "". Defaults to "".
            device (str, optional): Model GPU or CPU device (e.g. "/GPU:0", "/CPU:0"). Defaults to "/GPU:0".
        """

        super().__init__(
            name="EfficientDet_D1",
            id=id,
            device=device,
            source="TensorFlow Hub",
            info="EfficientDet model, with D1 architecture",
        )

        # Model
        with tf.device(self.device):
            self.model = hub.load("https://tfhub.dev/tensorflow/efficientdet/d1/1")

    def inference_batch(
        self, batch: pa.RecordBatch, view: str, uri_prefix: str, threshold: float = 0.0
    ) -> list[list[arrow_types.ObjectAnnotation]]:
        """Inference pre-annotation for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            view (str): Dataset view
            uri_prefix (str): URI prefix for media files
            threshold (float, optional): Confidence threshold. Defaults to 0.0.

        Returns:
            list[list[arrow_types.ObjectAnnotation]]: Model inferences as lists of ObjectAnnotation
        """

        objects = []

        # TF.Hub Models don't support image batches, so iterate manually
        for x in range(batch.num_rows):
            # Preprocess image
            im = batch[view][x].as_py(uri_prefix).as_pillow()
            im_tensor = tf.expand_dims(tf.keras.utils.img_to_array(im), 0)
            im_tensor = tf.image.convert_image_dtype(im_tensor, dtype="uint8")

            # Inference
            output = self.model(im_tensor)

            # Process model outputs
            objects.append(
                [
                    arrow_types.ObjectAnnotation(
                        id=shortuuid.uuid(),
                        view_id=view,
                        bbox=xyxy_to_xywh(
                            [
                                output["detection_boxes"][0][i][1],
                                output["detection_boxes"][0][i][0],
                                output["detection_boxes"][0][i][3],
                                output["detection_boxes"][0][i][2],
                            ]
                        ),
                        bbox_confidence=float(output["detection_scores"][0][i]),
                        bbox_source=self.id,
                        category_id=int(output["detection_classes"][0][i]),
                        category_name=coco_names_91(output["detection_classes"][0][i]),
                    )
                    for i in range(int(output["num_detections"]))
                    if output["detection_scores"][0][i] > threshold
                ]
            )
        return objects
