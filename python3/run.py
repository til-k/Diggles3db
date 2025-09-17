from lib.parse_3db import parse_3db_file
from lib.export import export_to_gltf
import os

input_folder = './assets/in'
output_folder = './assets/out'

load_all = False
selected_models = ["ringe.3db"]

for filename in os.listdir(input_folder):
    if load_all or (not load_all and filename in selected_models):
        if filename.endswith('.3db'):
            model_path = os.path.join(input_folder, filename)
            print(f'Loading model from {model_path}')
            with open(model_path, 'rb') as f:
                file_data = f.read()
                model = parse_3db_file(file_data)
                export_to_gltf(model, filename.removesuffix('.3db'), output_folder)
