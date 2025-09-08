import struct
from dataclasses import dataclass
from typing import List, Dict, Tuple

# FIXME: Surely theres a nice python library already for this
class Deserializer:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def advance(self, count: int):
        self.offset += count

    def read_u8(self):
        value = struct.unpack_from('B', self.data, self.offset)[0]
        self.advance(struct.calcsize('B'))
        return value

    def read_u16(self) -> int:
        value = struct.unpack_from('H', self.data, self.offset)[0]
        self.advance(struct.calcsize('H'))
        return value

    def read_u32(self) -> int:
        value = struct.unpack_from('I', self.data, self.offset)[0]
        self.advance(struct.calcsize('I'))
        return value

    def read_string(self) -> str:
        length = self.read_u32() 
        string = struct.unpack_from(f'{length}s', self.data, self.offset)[0]
        self.advance(length)
        return string

    def read_f32(self) -> float:
        value = struct.unpack_from('f', self.data, self.offset)[0]
        self.advance(struct.calcsize('f'))
        return value

    def read_vec3(self) -> (float, float, float):
        x = self.read_f32()
        y = self.read_f32()
        z = self.read_f32()
        return (x, y, z)

@dataclass
class KeyframeMesh:
    material: int
    unknown: int
    triangles: int
    texture_coordinates: int
    vertices: int
    brighness: int

@dataclass
class Keyframe:
    meshes: List[KeyframeMesh]

@dataclass
class Material:
    name: str
    texture_path: str
    _unknown: int = 0

@dataclass
class Animation:
    name: str
    keyframes: List[int]

@dataclass
class Model:
    db_version: str
    name: str
    materials: List[Material]
    keyframes: List[Keyframe]
    objects: Dict[str, int]
    animations: List[Animation]
    triangle_data: List[List[int]]
    texture_coordinates_data: List[List[Tuple[float, float]]]
    vertices_data: List[List[Tuple[float, float, float]]]
    brightness_data: List[List[int]]    


# Basic python3 implementation of the same logic as the C# and python2.7
# implementations 
def parse_3db_file(raw_data):

    deserializer = Deserializer(raw_data)

    # Read DB version
    db_version = deserializer.read_string()

    # Read name
    name = deserializer.read_string()

    # Read material count
    material_count = deserializer.read_u16()

    # Read materials
    materials = []
    for _ in range(material_count):
        material_name = deserializer.read_string()
        material_texture_path = deserializer.read_string()
        # TODO: this might be a material type?
        material_unknown = deserializer.read_u32()

        material = Material(material_name, material_texture_path, material_unknown)
        materials.append(material)

    # Read mesh count
    # TODO: I probably wouldnt call this "mesh count", instead its the number of animation keyframes.
    # each keyframe defines each mesh again
    # I think link_triangles links into the appropriapte for the corresponding mesh
    # the actual mesh count would be the number of defined meshes per keyframe, which is mesh_link_count. this count seems to always be the same, e.g. baby has one mesh for the hat and one for the body, and each keyframe has different points for those two
    # I _think_ this is a size optimization -> Vertices, triangles, uvs, are stored only once, but can be combined/referenced in each keyframe
    # this might be standard in 3D formats, but I'm not sure
    # I suspect that animation than references a list of these keyframes
    keyframe_count = deserializer.read_u32()

    # Read meshes
    keyframes = []
    for _ in range(keyframe_count):
        # TODO: check if this EVER changes - it seems to always be the same. e.g. if a model has 2 meshes, this number is always 2
        meshes_in_keyframe_count = deserializer.read_u16()

        meshes_in_keyframe = []
        for _ in range(meshes_in_keyframe_count):
            kf_material_idx = deserializer.read_u16()
            # TODO: these might be normals which would change with each keyframe
            kf_unknown_idx = deserializer.read_u16()
            kf_triangles_idx = deserializer.read_u16()
            kf_texture_coordinates_idx = deserializer.read_u16()
            kf_vertices_idx = deserializer.read_u16()
            kf_brightness_idx = deserializer.read_u16()

            link = KeyframeMesh(kf_material_idx, kf_unknown_idx, kf_triangles_idx,
                            kf_texture_coordinates_idx, kf_vertices_idx,
                            kf_brightness_idx)
            meshes_in_keyframe.append(link)

        unknown1 = deserializer.read_vec3()
        unknown2 = deserializer.read_vec3()
        deserializer.advance(0x80)
        deserializer.advance(2)
        deserializer.advance(0x30)
        deserializer.advance(2)

        keyframe = Keyframe(meshes_in_keyframe)
        keyframes.append(keyframe)

    # Read object data
    key_value_pair_count = deserializer.read_u16()
    objects = {}
    for _ in range(key_value_pair_count):
        key = deserializer.read_string()
        object_count = deserializer.read_u16()
        objects[key] = []
        for _ in range(object_count):
            objects[key].append(deserializer.read_u32())

    # Read animation data
    animations = []
    animation_count = deserializer.read_u16()
    for _ in range(animation_count):
        animation_name = deserializer.read_string()

        some_count = deserializer.read_u16()
        mesh_indices = []
        for _ in range(some_count):
            mesh_indices.append(deserializer.read_u32())

        # Read and ignore unknown values
        deserializer.read_u16()
        deserializer.read_f32()
        deserializer.read_string()
        deserializer.read_vec3()
        deserializer.read_vec3()

        animation = Animation(animation_name, mesh_indices)
        animations.append(animation)

    # Skip shadows
    shadow_count = deserializer.read_u16()
    for _ in range(shadow_count):
        deserializer.advance(32 * 32)

    # Read Cube maps?
    cube_map_count = deserializer.read_u16()
    for _ in range(cube_map_count):
        width = deserializer.read_u16()
        height = deserializer.read_u16()
        deserializer.read_u16()
        deserializer.read_u16()
        # Skip pixel data
        deserializer.advance(width * height)

    # Read triangles
    triangle_count = deserializer.read_u16()

    # Read texture coordinates?
    texture_coordinate_count = deserializer.read_u16()

    # Read vertices
    vertex_count = deserializer.read_u16()

    # Read brightness
    brightness_count = deserializer.read_u16()

    unknown_count = deserializer.read_u32()

    # Read triangle counts
    triangle_counts = []
    for _ in range(triangle_count):
        count = deserializer.read_u16()
        triangle_counts.append(count)

    texture_coordinate_counts = []
    for _ in range(texture_coordinate_count):
        texture_coordinate_counts.append(deserializer.read_u16())

    vertex_counts = []
    for _ in range(vertex_count):
        vertex_counts.append(deserializer.read_u16())

    brightness_counts = []
    for _ in range(brightness_count):
        brightness_counts.append(deserializer.read_u16())

    for _ in range(unknown_count):
        deserializer.advance(20)

    # Read actual triangle data
    triangle_data = []
    for i in range(triangle_count):
        count = triangle_counts[i]
        triangles = []
        for _ in range(count):
            triangles.append(deserializer.read_u16())
        triangle_data.append(triangles)

    # Read texture coordinates data
    texture_coordinates_data = []
    for i in range(texture_coordinate_count):
        count = texture_coordinate_counts[i]
        texture_coordinates = []
        for _ in range(count):
            u = deserializer.read_f32()
            v = deserializer.read_f32()
            texture_coordinates.append((u, v))
        texture_coordinates_data.append(texture_coordinates)

    # Read vertices data
    vertices_data = []
    for i in range(vertex_count):
        count = vertex_counts[i]
        vertices = []
        for _ in range(count):
            x = deserializer.read_u16() / float(0xffff)
            y = deserializer.read_u16() / float(0xffff)
            z = deserializer.read_u16() / float(0xffff)
            vertices.append((x, y, z))
        vertices_data.append(vertices)

    # Read brightness data
    brightness_data = []
    for i in range(brightness_count):
        count = brightness_counts[i]
        brightness = []
        for _ in range(count):
            brightness.append(deserializer.read_u8())
        brightness_data.append(brightness)


    result = Model(db_version, name, materials, keyframes, objects, animations,
            triangle_data, texture_coordinates_data, vertices_data, brightness_data)
    return result

