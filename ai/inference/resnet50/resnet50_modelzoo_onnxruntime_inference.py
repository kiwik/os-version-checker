import json
import time

import numpy as np  # we're going to use numpy to process input and output data
import onnxruntime  # to inference ONNX models, we use the ONNX Runtime
from PIL import Image


def load_labels(path):
    with open(path) as f:
        data = json.load(f)
    return np.asarray(data)


def preprocess(_input_data):
    # convert the input data into the float32 input
    img_data = _input_data.astype('float32')

    # normalize
    mean_vec = np.array([0.485, 0.456, 0.406])
    stddev_vec = np.array([0.229, 0.224, 0.225])
    norm_img_data = np.zeros(img_data.shape).astype('float32')
    for i in range(img_data.shape[0]):
        norm_img_data[i, :, :] = (img_data[i, :, :] / 255 - mean_vec[i]) / \
                                 stddev_vec[i]

    # add batch channel
    norm_img_data = norm_img_data.reshape(1, 3, 224, 224).astype('float32')
    return norm_img_data


def softmax(x):
    x = x.reshape(-1)
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=0)


def postprocess(result):
    return softmax(np.array(result)).tolist()


# Run the model on the backend
session = onnxruntime.InferenceSession('resnet50v2/resnet50v2.onnx', None)
# get the name of the first input of the model
input_name = session.get_inputs()[0].name
labels = load_labels('imagenet-simple-labels.json')

input_file_names = ['dog', 'plane']
file_data = list()
loop_times = 500

for one in input_file_names:
    image = Image.open('images/{}.jpg'.format(one))
    image_data = np.array(image).transpose(2, 0, 1)
    input_data = preprocess(image_data)
    file_data.append({'input_data': input_data, 'size': image.size})

start = time.time()
for i in range(loop_times):
    for _file in file_data:
        raw_result = session.run([], {input_name: _file.get('input_data')})
        if i + 1 == loop_times:
            _file['output_data'] = raw_result
    # if i % 50 == 0:
    #     print('......{}%'.format(int(i / loop_times * 100)))
end = time.time()

for _file in file_data:
    res = postprocess(_file.get('output_data'))
    _file['top'] = labels[np.flip(np.squeeze(np.argsort(res)))[:4]]

print('========================================')
for _name, _data in zip(input_file_names, file_data):
    print('{0:10}\t{1:10}\t{2:50}'.format(_name,
                                          str(_data.get('size')),
                                          str(_data.get('top'))))
print('========================================')
inference_time = np.round((end - start), 2)
print('{} times inference time: {}s'.format(loop_times * len(input_file_names),
                                            str(inference_time)))
print('========================================')
