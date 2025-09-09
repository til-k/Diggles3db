import struct
import operator
from gltflib import (
    GLTF, GLTFModel, Asset, Scene, Node, Mesh, Primitive, Attributes, Buffer, BufferView, Accessor, AccessorType,
    BufferTarget, ComponentType, FileResource, PBRMetallicRoughness, Texture, Image, Material, TextureInfo, Sampler, Animation, AnimationSampler, Channel, Target)

from lib.parse_3db import Model
from typing import List, Dict, Tuple
import os

def transform_point(p: Tuple[float, float, float]):
    # TODO: Check why scale and axis flip work the way they do. It looks good when importing the model in Blender.
    scale = 100
    # Flip Y-axis and Z-axis to match the glTF coordinate system
    result = ((p[0] - 0.5) * scale, - (p[1] -0.5) * scale, - (p[2] - 0.5) * scale)
    return result

def build_vertices_array(triangles: List[int], points: List[Tuple[float, float, float]]):
    vertices = [points[index] for index in triangles]
    return vertices

def export_to_gltf(model: Model, name: str, output_path: str):
    nodes = []
    vertex_byte_array = bytearray()
    uv_byte_array = bytearray()
    index_byte_array = bytearray()
    accessors = []
    for [node_name, animations] in model.objects.items():
        kf_meshes = []
        triangle_idx_3db_to_gltf_accessor = dict()
        # Load first keyframe as base meshes, rest as morph targets
        for kf_mesh in model.keyframes[0].meshes:
            triangles = model.triangle_data[kf_mesh.triangles]
            points = model.vertices_data[kf_mesh.vertices]
            texture_coordinates = model.texture_coordinates_data[kf_mesh.texture_coordinates]
            vertices = [transform_point(p) for p in points]

            vertex_data_start = len(vertex_byte_array)
            for vertex in vertices:
                for value in vertex:
                    vertex_byte_array.extend(struct.pack('f', value))

            mins = [min([operator.itemgetter(i)(vertex) for vertex in vertices]) for i in range(3)]
            maxs = [max([operator.itemgetter(i)(vertex) for vertex in vertices]) for i in range(3)]

            texture_coords_start = len(uv_byte_array)
            for t in texture_coordinates:
                for value in t:
                    uv_byte_array.extend(struct.pack('f', value))

            indices_start = len(index_byte_array)
            for index in triangles:
                index_byte_array.extend(struct.pack('I', index))

            position_index = len(accessors)
            accessors.append(Accessor(bufferView=0, byteOffset=vertex_data_start, componentType=ComponentType.FLOAT.value, count=len(vertices),
                                type=AccessorType.VEC3.value, min=mins, max=maxs))

            texture_coords_index = len(accessors)
            accessors.append(Accessor(bufferView=1, byteOffset=texture_coords_start, componentType=ComponentType.FLOAT.value, count=len(texture_coordinates),
                                type=AccessorType.VEC2.value))

            indices_index = len(accessors)
            accessors.append(Accessor(bufferView=2, byteOffset=indices_start, componentType=ComponentType.UNSIGNED_INT.value, count=len(triangles),
                                type=AccessorType.SCALAR.value))
            triangle_idx_3db_to_gltf_accessor[kf_mesh.triangles] = indices_index

            mesh_index = len(kf_meshes)
            kf_meshes.append(Mesh(primitives=[Primitive(attributes=Attributes(POSITION=position_index, TEXCOORD_0=texture_coords_index), indices=indices_index, material=kf_mesh.material, targets=[])]))

            nodes.append(Node(name=node_name, mesh=mesh_index))

        keyframes = model.keyframes[1:10]
        for kf_idx, kf in enumerate(keyframes):
            current_mesh_idx = 0
            for kf_mesh in kf.meshes:
                points = model.vertices_data[kf_mesh.vertices]
                texture_coordinates = model.texture_coordinates_data[kf_mesh.texture_coordinates]
                vertices = [transform_point(p) for p in points]

                vertex_data_start = len(vertex_byte_array)
                for vertex in vertices:
                    for value in vertex:
                        vertex_byte_array.extend(struct.pack('f', value))
                mins = [min([operator.itemgetter(i)(vertex) for vertex in vertices]) for i in range(3)]
                maxs = [max([operator.itemgetter(i)(vertex) for vertex in vertices]) for i in range(3)]

                texture_coords_start = len(uv_byte_array)
                for t in texture_coordinates:
                    for value in t:
                        uv_byte_array.extend(struct.pack('f', value))

                position_index = len(accessors)
                accessors.append(Accessor(bufferView=0, byteOffset=vertex_data_start, componentType=ComponentType.FLOAT.value, count=len(vertices),
                                    type=AccessorType.VEC3.value, min=mins, max=maxs))

                texture_coords_index = len(accessors)
                accessors.append(Accessor(bufferView=1, byteOffset=texture_coords_start, componentType=ComponentType.FLOAT.value, count=len(texture_coordinates),
                                    type=AccessorType.VEC2.value))

                mesh = kf_meshes[current_mesh_idx]
                mesh.primitives[0].targets.append(Attributes(POSITION=position_index, TEXCOORD_0=texture_coords_index))
                current_mesh_idx+=1


    images = []
    texture_resources = []
    gltfsamplers = []
    gltftextures = []  
    materials = []
    for material in model.materials:
        texture_name = material.name
        # check if file exists in m256 or m128 asset folder folder, take the highest version
        # TODO: make this check the other folders
        possible_paths = [
            "./assets/in/m256/",
            "./assets/in/m128/"
        ]
        FILE_ENDING = ".tga"
        for path_suffix in possible_paths:
            full_path = os.path.join(path_suffix, texture_name + FILE_ENDING)
            if os.path.isfile(full_path):
                images.append(Image(uri=full_path))
                texture_resources.append(FileResource(full_path))
                
                # TODO: this adds a new sampler, texture and material per image texture, all with default values. There may be a cleaner way to handle this.
                current_idx = len(gltftextures)
                gltfsamplers.append(Sampler())
                gltftextures.append(Texture(sampler=current_idx,source=current_idx))
                pbr = PBRMetallicRoughness(baseColorTexture=TextureInfo(index=current_idx))
                gltf_material = Material(pbrMetallicRoughness=pbr)
                materials.append(gltf_material)
                break

    animation_in_byte_array = bytearray()
    animation_out_byte_array = bytearray()
    ain_min = 0
    ain_max = 0
    for i in range(1, 10):
        ain_val = (0.0 + ((i-1)/10.0))
        if ain_val < ain_min: ain_min = ain_val
        if ain_val > ain_max: ain_max = ain_val
        animation_in_byte_array.extend(struct.pack('f', ain_val))
        for j in range(1, 10):
            if i==j:
                animation_out_byte_array.extend(struct.pack('f', 1.0))
            else:
                animation_out_byte_array.extend(struct.pack('f', 0.0))
    accessor_a_in_idx = len(accessors)
    ain_mins = []
    ain_maxs = []
    ain_mins.append(ain_min)
    ain_maxs.append(ain_max)
    accessors.append(Accessor(bufferView=3, byteOffset=0, componentType=ComponentType.FLOAT.value, count=9,
                        type=AccessorType.SCALAR.value, min=ain_mins, max=ain_maxs))
    accessor_a_out_idx = len(accessors)
    accessors.append(Accessor(bufferView=4, byteOffset=0, componentType=ComponentType.FLOAT.value, count=81,
                        type=AccessorType.SCALAR.value))
    anim = Animation(channels=[Channel(sampler=0,target=Target(node=0, path="weights"))], samplers=[AnimationSampler(input=accessor_a_in_idx, output=accessor_a_out_idx)])
    animations = [anim]

    model = GLTFModel(
        asset=Asset(version='2.0'),
        scenes=[Scene(nodes=[idx for idx, _ in enumerate(nodes)])],
        nodes=nodes,
        buffers=[Buffer(byteLength=len(vertex_byte_array), uri= name + '_vertices.bin'), 
                 Buffer(byteLength=len(uv_byte_array), uri= name + '_uvs.bin'), 
                 Buffer(byteLength=len(index_byte_array), uri=name + '_indices.bin'),
                 Buffer(byteLength=len(animation_in_byte_array), uri=name + '_ain.bin'),
                 Buffer(byteLength=len(animation_out_byte_array), uri=name + '_aout.bin')],
        bufferViews=[BufferView(buffer=0, byteOffset=0, byteLength=len(vertex_byte_array), target=BufferTarget.ARRAY_BUFFER.value, byteStride=12),
                     BufferView(buffer=1, byteOffset=0, byteLength=len(uv_byte_array), target=BufferTarget.ARRAY_BUFFER.value, byteStride=8),
                     BufferView(buffer=2, byteOffset=0, byteLength=len(index_byte_array), target=BufferTarget.ELEMENT_ARRAY_BUFFER.value),
                     BufferView(buffer=3, byteOffset=0, byteLength=len(animation_in_byte_array)),
                     BufferView(buffer=4, byteOffset=0, byteLength=len(animation_out_byte_array))],
        accessors=accessors,
        meshes=kf_meshes,
        materials=materials,
        samplers=gltfsamplers,
        textures=gltftextures,
        images=images,
        animations=animations
    )


    resources = [FileResource(name + '_vertices.bin', data=vertex_byte_array),
                 FileResource(name + '_uvs.bin', data=uv_byte_array),
                 FileResource(name + '_indices.bin', data=index_byte_array),     
                 FileResource(name + '_ain.bin', data=animation_in_byte_array),
                 FileResource(name + '_aout.bin', data=animation_out_byte_array)]
    resources.extend(texture_resources)
    gltf = GLTF(model=model, resources=resources)
    gltf.export_gltf(output_path + "/" + name + '_out.gltf')
    print('Converted: ' + name)
