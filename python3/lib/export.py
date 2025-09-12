import struct
import operator
from gltflib import (
    GLTF, GLTFModel, Asset, Scene, Node, Mesh, Primitive, Attributes, Buffer, BufferView, Accessor, AccessorType,
    BufferTarget, ComponentType, FileResource, PBRMetallicRoughness, Texture, Image, Material, TextureInfo, Sampler, Animation, AnimationSampler, Channel, Target)

from lib.parse_3db import Model
from lib.math_util import Vector3, Vector2
from typing import List, Dict, Tuple
import os

def transform_vertex(v: Vector3) -> Vector3: 
    # TODO: Check why scale and axis flip work the way they do. It looks good when importing the model in Blender.
    scale = 100
    # Flip Y-axis and Z-axis to match the glTF coordinate system
    return Vector3((v.x - 0.5) * scale, - (v.y -0.5) * scale, - (v.z - 0.5) * scale)
def export_to_gltf(model: Model, name: str, output_path: str):

    nodes = []
    object_root_nodes = []
    accessors = []

    images = []
    texture_resources = []
    gltfsamplers = []
    gltftextures = []  
    materials = []

    vertex_byte_array = bytearray()
    uv_byte_array = bytearray()
    index_byte_array = bytearray()

    animation_in_byte_array = bytearray()
    animation_out_byte_array = bytearray()
    gltf_animations = []

    sampler_idx = 0

    for [node_name, animation_idxs] in model.objects.items():
        kf_meshes = []
        base_node = Node(name=node_name, children=[])
        base_node_idx = len(nodes)
        nodes.append(base_node)
        object_root_nodes.append(base_node_idx)
        for animation_idx in animation_idxs:
            animation = model.animations[animation_idx]
            keyframes_in_animation = [kf for index, kf in enumerate(model.keyframes) if index in animation.keyframes]
            # Invert structure from "list of frames, with list of all meshes" to "list of meshes with list of its frames"
            meshes_with_frames = [[keyframes_in_animation[i].meshes[j] for i in range(len(keyframes_in_animation))] for j in range(len(keyframes_in_animation[0].meshes))]
            #meshes_with_frames = list(map(list, zip(*model.keyframes)))
            for frames in meshes_with_frames:            
                keyframe_len = len(frames)
                base_vertices = None
                base_indices = None
                base_mesh = None
                # Load first keyframe as base meshes, rest as morph target
                for frame in frames:
                    vertices = [transform_vertex(p) for p in model.vertex_data[frame.vertices]]
                    if base_vertices == None:   base_vertices = vertices
                    else:                       vertices = [vertex - base_vertex for vertex, base_vertex in zip(vertices, base_vertices)]
                    mins = list(map(min, zip(*vertices)))
                    maxs = list(map(max, zip(*vertices)))
                    vertex_data_start = len(vertex_byte_array)
                    [vertex_byte_array.extend(struct.pack('fff', v.x, v.y, v.z)) for v in vertices]
                    vertex_accessor_idx = len(accessors)
                    accessors.append(Accessor(bufferView=0, byteOffset=vertex_data_start, componentType=ComponentType.FLOAT.value, count=len(vertices),
                                        type=AccessorType.VEC3.value, min=mins, max=maxs))
                    
                    texture_coordinates = model.texture_coordinates_data[frame.texture_coordinates]
                    texture_coords_start = len(uv_byte_array)
                    [uv_byte_array.extend(struct.pack('ff', uv.x, uv.y)) for uv in texture_coordinates]
                    texture_coords_accessors_index = len(accessors)
                    accessors.append(Accessor(bufferView=1, byteOffset=texture_coords_start, componentType=ComponentType.FLOAT.value, count=len(texture_coordinates),
                                        type=AccessorType.VEC2.value))
                    
                    if base_indices == None:
                        base_indices = model.triangle_data[frame.triangles]
                        indices_start = len(index_byte_array)
                        [index_byte_array.extend(struct.pack('I', index)) for index in base_indices]  
                        indices_accessor_index = len(accessors)
                        accessors.append(Accessor(bufferView=2, byteOffset=indices_start, componentType=ComponentType.UNSIGNED_INT.value, count=len(base_indices),
                                            type=AccessorType.SCALAR.value))

                    if base_mesh == None:
                        mesh_index = len(kf_meshes)
                        base_mesh = Mesh(primitives=[Primitive(attributes=Attributes(POSITION=vertex_accessor_idx, TEXCOORD_0=texture_coords_accessors_index), indices=indices_accessor_index, material=frame.material, targets=[])])
                        kf_meshes.append(base_mesh)
                        mesh_node_idx = len(nodes)
                        nodes.append(Node(name=node_name, mesh=mesh_index))
                        base_node.children.append(mesh_node_idx)
                    else:                
                        base_mesh.primitives[0].targets.append(Attributes(POSITION=vertex_accessor_idx, TEXCOORD_0=texture_coords_accessors_index))
            
                # TODO: Method to get min & max is a lazy hack right now
                ain_min = 1000000
                ain_max = 0
                a_in_byteOffset = len(animation_in_byte_array)
                a_out_byteOffset = len(animation_out_byte_array)
                for i in range(1, keyframe_len+1):
                    ain_val = (i/float(keyframe_len)) * 50
                    if ain_val < ain_min: ain_min = ain_val
                    if ain_val > ain_max: ain_max = ain_val
                    animation_in_byte_array.extend(struct.pack('f', ain_val))
                    for j in range(1, keyframe_len+1):
                        if i==(j+1):
                            animation_out_byte_array.extend(struct.pack('f', 1.0))
                        else:
                            animation_out_byte_array.extend(struct.pack('f', 0.0))
                accessor_a_in_idx = len(accessors)
                accessors.append(Accessor(bufferView=3, byteOffset=a_in_byteOffset, componentType=ComponentType.FLOAT.value, count=keyframe_len,
                                    type=AccessorType.SCALAR.value, min=[ain_min], max=[ain_max]))
                accessor_a_out_idx = len(accessors)
                accessors.append(Accessor(bufferView=4, byteOffset=a_out_byteOffset, componentType=ComponentType.FLOAT.value, count=keyframe_len*(keyframe_len-1),
                                    type=AccessorType.SCALAR.value))
                gltf_anim = Animation(name=animation.name,
                                channels=[Channel(sampler=0,target=Target(node=len(nodes)-1, path="weights"))],  # TODO: not good, but latest node should be the one that is targeted by this animation?
                                samplers=[AnimationSampler(input=accessor_a_in_idx, output=accessor_a_out_idx)])
                gltf_animations.append(gltf_anim)


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

    model = GLTFModel(
        asset=Asset(version='2.0'),
        scenes=[Scene(nodes=[idx for idx, _ in enumerate(object_root_nodes)])],
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
        animations=gltf_animations
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
