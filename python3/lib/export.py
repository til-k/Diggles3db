import struct
import operator
from gltflib import (
    GLTF, GLTFModel, Asset, Scene, Node, Mesh, Primitive, Attributes, Buffer, BufferView, Accessor, AccessorType,
    BufferTarget, ComponentType, FileResource, PBRMetallicRoughness, Texture, Image, Material, TextureInfo, Sampler)

from lib.parse_3db import Model
from typing import List, Dict, Tuple
import os

def transform_point(p: Tuple[float, float, float]):
    scale = 100
    result = ((p[0] - 0.5) * scale, (p[1] -0.5) * scale, (p[2] - 0.5) * scale)
    return result

def build_vertices_array(triangles: List[int], points: List[Tuple[float, float, float]]):
    vertices = [points[index] for index in triangles]
    return vertices

def export_to_gltf(model: Model, name: str, output_path: str):
    nodes = []
    meshes = []
    accessors = []

    vertex_byte_array = bytearray()
    index_byte_array = bytearray()

    kf_idx = 0
    kf = model.keyframes[kf_idx]
    for mesh in kf.meshes:
        triangles = model.triangle_data[mesh.triangles]
        points = model.vertices_data[mesh.vertices]
        texture_coordinates = model.texture_coordinates_data[mesh.texture_coordinates]
        vertices = [transform_point(p) for p in points]

        vertex_data_start = len(vertex_byte_array)
        for vertex in vertices:
            for value in vertex:
                vertex_byte_array.extend(struct.pack('f', value))

        mins = [min([operator.itemgetter(i)(vertex) for vertex in vertices]) for i in range(3)]
        maxs = [max([operator.itemgetter(i)(vertex) for vertex in vertices]) for i in range(3)]

        texture_coords_start = len(vertex_byte_array)
        for t in texture_coordinates:
            for value in t:
                vertex_byte_array.extend(struct.pack('f', value))

        indices_start = len(index_byte_array)
        for index in triangles:
            index_byte_array.extend(struct.pack('I', index))

        position_index = len(accessors)
        accessors.append(Accessor(bufferView=0, byteOffset=vertex_data_start, componentType=ComponentType.FLOAT.value, count=len(vertices),
                            type=AccessorType.VEC3.value, min=mins, max=maxs))

        texture_coords_index = len(accessors)
        accessors.append(Accessor(bufferView=0, byteOffset=texture_coords_start, componentType=ComponentType.FLOAT.value, count=len(texture_coordinates),
                            type=AccessorType.VEC2.value))

        indices_index = len(accessors)
        accessors.append(Accessor(bufferView=1, byteOffset=indices_start, componentType=ComponentType.UNSIGNED_INT.value, count=len(triangles),
                            type=AccessorType.SCALAR.value))

        mesh_index = len(meshes)
        meshes.append(Mesh(primitives=[Primitive(attributes=Attributes(POSITION=position_index, TEXCOORD_0=texture_coords_index), indices=indices_index, material=mesh.material)]))
        nodes.append(Node(mesh=mesh_index))

    images = []
    texture_resources = []
    gltfsamplers = []
    gltftextures = []  
    materials = []
    for material in model.materials:
        texture_name = material.name.decode('utf-8')
        texture_resource = None
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
                current_idx = len(gltftextures) - 1
                gltfsamplers.append(Sampler())
                gltftextures.append(Texture(sampler=current_idx,source=current_idx))
                pbr = PBRMetallicRoughness(baseColorTexture=TextureInfo(index=current_idx))
                gltf_material = Material(pbrMetallicRoughness=pbr)
                materials.append(gltf_material)
                break

    model = GLTFModel(
        asset=Asset(version='2.0'),
        scenes=[Scene(nodes=[x for x in range(len(nodes))])],
        nodes=nodes,
        buffers=[Buffer(byteLength=len(vertex_byte_array), uri= name + '_vertices.bin'), Buffer(byteLength=len(index_byte_array), uri=name + '_indices.bin')],
        bufferViews=[BufferView(buffer=0, byteOffset=0, byteLength=len(vertex_byte_array), target=BufferTarget.ARRAY_BUFFER.value),
                     BufferView(buffer=1, byteOffset=0, byteLength=len(index_byte_array), target=BufferTarget.ELEMENT_ARRAY_BUFFER.value)],
        accessors=accessors,
        meshes=meshes,
        materials=materials,
        samplers=gltfsamplers,
        textures=gltftextures,
        images=images
    )


    resources = [FileResource(name + '_vertices.bin', data=vertex_byte_array),
                FileResource(name + '_indices.bin', data=index_byte_array)]
    resources.extend(texture_resources)
    gltf = GLTF(model=model, resources=resources)
    gltf.export_glb(output_path + "/" + name + '_out.glb')
    print('Converted: ' + name)
