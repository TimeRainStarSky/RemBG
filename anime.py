#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import onnxruntime as rt

SCALE: int = 255


def get_mask(
    session_infer: rt.InferenceSession,
    img: np.ndarray,
    size_infer: int = 1024,
):
    img = (img / SCALE).astype(np.float32)
    h_orig, w_orig = img.shape[:-1]

    if h_orig > w_orig:
        h_infer, w_infer = (size_infer, int(size_infer * w_orig / h_orig))
    else:
        h_infer, w_infer = (int(size_infer * h_orig / w_orig), size_infer)

    h_padding, w_padding = size_infer - h_infer, size_infer - w_infer
    img_infer = np.zeros([size_infer, size_infer, 3], dtype=np.float32)
    img_infer[
        h_padding // 2 : h_padding // 2 + h_infer,
        w_padding // 2 : w_padding // 2 + w_infer,
    ] = cv2.resize(img, (w_infer, h_infer))
    img_infer = np.transpose(img_infer, (2, 0, 1))
    img_infer = img_infer[np.newaxis, :]

    mask = session_infer.run(None, {"img": img_infer})[0][0]
    mask = np.transpose(mask, (1, 2, 0))
    mask = mask[
        h_padding // 2 : h_padding // 2 + h_infer,
        w_padding // 2 : w_padding // 2 + w_infer,
    ]
    mask = cv2.resize(mask, (w_orig, h_orig))[:, :, np.newaxis]
    return mask


def save_image(
    *,
    img,
    output: Path,
    out_format,
):
    img = cv2.cvtColor(img, out_format)
    cv2.imwrite(str(output), img)


def operation(
    *,
    model: str,
    targets: List[str],
    alpha_min: float,
    alpha_max: float,
) -> None:

    session_infer = rt.InferenceSession(
        model,
        providers=[
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ],
    )

    img = cv2.cvtColor(cv2.imread(targets[0], cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = get_mask(session_infer, img)

    mask[mask < alpha_min] = 0.0
    mask[mask > alpha_max] = 1.0

    img_after = (mask * img + SCALE * (1 - mask)).astype(np.uint8)
    mask = (mask * SCALE).astype(np.uint8)
    img_after = np.concatenate([img_after, mask], axis=2, dtype=np.uint8)
    mask = mask.repeat(3, axis=2)

    save_image(
        img=img_after,
        output=targets[1],
        out_format=cv2.COLOR_BGRA2RGBA,
    )

    save_image(
        img=mask,
        output="matted_" + targets[1],
        out_format=cv2.COLOR_BGR2RGB,
    )


def get_opts():
    oparser = argparse.ArgumentParser()
    oparser.add_argument(
        "--model",
        default="isnetis.onnx",
    )
    oparser.add_argument(
        "--alpha-min",
        type=float,
        default=0.0,
    )
    oparser.add_argument(
        "--alpha-max",
        type=float,
        default=1.0,
    )
    return oparser.parse_known_args()


def main() -> None:
    (opts, targets) = get_opts()
    operation(
        model=opts.model,
        targets=targets,
        alpha_min=opts.alpha_min,
        alpha_max=opts.alpha_max,
    )


if __name__ == "__main__":
    main()
