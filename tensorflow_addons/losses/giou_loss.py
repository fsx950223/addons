# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Implements GIOU loss."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
from tensorflow_addons.utils import keras_utils


@keras_utils.register_keras_custom_object
class GIOULoss(tf.keras.losses.Loss):
    """Implements the GIOU loss function.

    GIOU loss was first introduced in the Generalized Intersection over Union paper
    (https://giou.stanford.edu/GIoU.pdf). GIOU loss is a patch for model which IOU
    is used in object detection.

    Usage:

    ```python
    fl = tfa.losses.GIOU()
    loss = fl(
      [[0.97], [0.91], [0.03]],
      [[1], [1], [0])
    print('Loss: ', loss.numpy())  # Loss: [[0.03045921]
                                            [0.09431068]
                                            [0.31471074]
    ```
    Usage with tf.keras API:

    ```python
    model = tf.keras.Model(inputs, outputs)
    model.compile('sgd', loss=tf.keras.losses.GIOULoss())
    ```

    Args
      name: Op name

    Returns:
      Weighted loss float `Tensor`. If `reduction` is `NONE`, this has the same
          shape as `y_true`; otherwise, it is scalar.

    Raises:
        ValueError: If the shape of `sample_weight` is invalid or value of
          `gamma` is less than zero
    """

    def __init__(self,
                 reduction=tf.keras.losses.Reduction.NONE,
                 name='giou_loss'):
        super(GIOULoss, self).__init__(name=name, reduction=reduction)

    def call(self, y_true, y_pred):
        return giou_loss(y_true, y_pred)

    def get_config(self):
        base_config = super(GIOULoss, self).get_config()
        return base_config


@keras_utils.register_keras_custom_object
def giou_loss(y_true, y_pred):
    """
    Args
        y_true: true targets tensor.
        y_pred: predictions tensor.
    
    Returns:
        Weighted loss float `Tensor`.
    """

    y_pred = tf.convert_to_tensor(y_pred)
    y_true = tf.cast(y_true, y_pred.dtype)
    giou = _giou(y_pred, y_true)

    # compute the final loss and return
    return 1 - giou


@tf.function
def _giou(b1, b2):
    b1_ymin = tf.minimum(b1[:, 0], b1[:, 2])
    b1_xmin = tf.minimum(b1[:, 1], b1[:, 3])
    b1_ymax = tf.maximum(b1[:, 0], b1[:, 2])
    b1_xmax = tf.maximum(b1[:, 1], b1[:, 3])
    b2_ymin = tf.minimum(b2[:, 0], b2[:, 2])
    b2_xmin = tf.minimum(b2[:, 1], b2[:, 3])
    b2_ymax = tf.maximum(b2[:, 0], b2[:, 2])
    b2_xmax = tf.maximum(b2[:, 1], b2[:, 3])
    b1_area = (b1_ymax - b1_ymin) * (b1_xmax - b1_xmin)
    b2_area = (b2_ymax - b2_ymin) * (b2_xmax - b1_xmin)
    illegal_area_indexes = tf.cast(
        tf.where(tf.logical_or(b1_area < 0, b2_area < 0)), tf.int32)
    valid_area_indexes = tf.cast(
        tf.where(tf.logical_and(b1_area >= 0, b2_area >= 0)), tf.int32)
    # if b1_area<0 or b2_area<0:
    #     return 0

    intersect_ymin = tf.maximum(b1_ymin, b2_ymin)
    intersect_xmin = tf.maximum(b1_xmin, b2_xmin)
    intersect_ymax = tf.minimum(b1_ymax, b2_ymax)
    intersect_xmax = tf.minimum(b1_xmax, b2_xmax)
    intersect_area = tf.maximum(0,
                                intersect_ymax - intersect_ymin) * tf.maximum(
                                    0, intersect_xmax - intersect_xmin)

    union_area = b1_area + b2_area - intersect_area
    iou = intersect_area / union_area
    indices = [valid_area_indexes, illegal_area_indexes]
    data = [
        tf.gather(iou, valid_area_indexes),
        tf.zeros([tf.shape(illegal_area_indexes)[0], 1], tf.float64)
    ]
    iou = tf.dynamic_stitch(indices, data)
    bc_ymin = tf.minimum(b1_ymin, b2_ymin)
    bc_xmin = tf.minimum(b1_xmin, b2_xmin)
    bc_ymax = tf.maximum(b1_ymax, b2_ymax)
    bc_xmax = tf.maximum(b1_xmax, b2_xmax)

    enclose_area = tf.maximum(0, bc_ymax - bc_ymin) * tf.maximum(
        0, bc_xmax - bc_xmin)
    giou = iou - (enclose_area - union_area) / enclose_area
    return giou