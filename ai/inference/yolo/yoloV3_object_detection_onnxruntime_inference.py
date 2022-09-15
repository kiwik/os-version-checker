import time

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import onnxruntime
from PIL import Image


# This function is from yolo3.utils.letterbox_image
def letterbox_image(image, size):
    '''Resize image with unchanged aspect ratio using padding'''
    iw, ih = image.size
    w, h = size
    scale = min(w / iw, h / ih)
    nw = int(iw * scale)
    nh = int(ih * scale)

    image = image.resize((nw, nh), Image.Resampling.BICUBIC)
    new_image = Image.new('RGB', size, (128, 128, 128))
    new_image.paste(image, ((w - nw) // 2, (h - nh) // 2))
    return new_image


def preprocess(img):
    model_image_size = (416, 416)
    boxed_image = letterbox_image(img, tuple(reversed(model_image_size)))
    image_data = np.array(boxed_image, dtype='float32')
    image_data /= 255.
    image_data = np.transpose(image_data, [2, 0, 1])
    image_data = np.expand_dims(image_data, 0)
    return image_data


def postprocess(img_name, boxes, scores, indices):
    objects_identified = indices.shape[0]
    out_boxes, out_scores, out_classes = [], [], []
    if objects_identified > 0:
        for idx_ in indices:
            out_classes.append(classes[idx_[1]])
            out_scores.append(scores[tuple(idx_)])
            idx_1 = (idx_[0], idx_[2])
            out_boxes.append(boxes[idx_1])
        print("{} objects identified in {}.jpg, include {}".format(
            str(objects_identified), img_name, out_classes))
    else:
        print("No objects identified in {}.jpg.".format(img_name))
    return out_boxes, out_scores, out_classes, objects_identified


def display_candidate_boxes(image, boxes, image_name='sample', num_boxes=300):
    img = np.array(image)
    plt.figure()
    fig, ax = plt.subplots(1, figsize=(12, 9))
    ax.imshow(img)

    candidate_boxes = np.random.choice(boxes.shape[1], num_boxes,
                                       replace=False)

    for c in candidate_boxes:
        y1, x1, y2, x2 = boxes[0][c]
        color = 'blue'
        box_h = (y2 - y1)
        box_w = (x2 - x1)
        bbox = patches.Rectangle((x1, y1), box_w, box_h, linewidth=2,
                                 edgecolor=color, facecolor='none')
        ax.add_patch(bbox)

    plt.axis('off')
    # save image
    plt.savefig("yolov3/" + image_name + "-candidate.jpg", bbox_inches='tight',
                pad_inches=0.0)
    # plt.show()


def display_objdetect_image(image, out_boxes, out_classes,
                            image_name='sample', objects_identified=None,
                            save=True):
    plt.figure()
    fig, ax = plt.subplots(1, figsize=(12, 9))
    ax.imshow(image)
    if not objects_identified:
        objects_identified = len(out_boxes)

    for i in range(objects_identified):
        y1, x1, y2, x2 = out_boxes[i]
        class_pred = out_classes[i]
        color = 'blue'
        box_h = (y2 - y1)
        box_w = (x2 - x1)
        bbox = patches.Rectangle((x1, y1), box_w, box_h, linewidth=2,
                                 edgecolor=color, facecolor='none')
        ax.add_patch(bbox)
        plt.text(x1, y1, s=class_pred, color='white', verticalalignment='top',
                 bbox={'color': color, 'pad': 0})

    plt.axis('off')
    # save image
    image_name = "yolov3/" + image_name + "-det.jpg"
    plt.savefig(image_name, bbox_inches='tight', pad_inches=0.0)
    if save:
        # plt.show()
        pass


input_file_names = ['horses', 'blueangels', 'road']
file_data = list()
loop_times = 30
classes = [line.rstrip('\n') for line in open('coco_classes.txt')]

# Let us initialize an inference session with our yoloV3 model
session = onnxruntime.InferenceSession('yolov3/yolov3.onnx')

for one in input_file_names:
    img = Image.open('../images/{}.jpg'.format(one))
    # Preprocess input according to the functions specified above
    img_data = preprocess(img)
    img_size = np.array([img.size[1], img.size[0]], dtype=np.float32).reshape(
        1, 2)
    file_data.append({'input_raw': img,
                      'input_data': img_data,
                      'input_size': img_size})

start = time.time()
for _i in range(loop_times):
    for _file in file_data:
        boxes, scores, indices = session.run(
            None, {"input_1": _file.get('input_data'),
                   "image_shape": _file.get('input_size')})
        if _i + 1 == loop_times:
            _file['output_data'] = (boxes, scores, indices)
end = time.time()

inference_time = np.round(end - start, 2)
print('========================================')
print("{} times inference time: {} sec".format(
    loop_times * len(input_file_names), str(inference_time)))
print('========================================')

for _one, _file in zip(input_file_names, file_data):
    output = _file.get('output_data')
    out_boxes, out_scores, out_classes, objects_identified = postprocess(
        _one,
        output[0],
        output[1],
        output[2])
    # display_candidate_boxes(img, boxes, "horse")
    display_objdetect_image(_file.get('input_raw'), out_boxes, out_classes,
                            _one)
