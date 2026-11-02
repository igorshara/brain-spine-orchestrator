"""Render the illustration of the controller, communicator and implant chain.

Primitive geometry only, no downloads. Generic devices, not any manufacturer's design.
Run: blender -b -P tools/blender/system_scene.py -- OUT_DIR [WIDTH] [SAMPLES]
Writes system_scene.png with transparency and system_scene.json with the image
position of each device, so the page can place its markers from measured values.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
OUT = Path(args[0])
WIDTH = int(args[1]) if len(args) > 1 else 900
SAMPLES = int(args[2]) if len(args) > 2 else 96
HEIGHT = WIDTH * 6 // 5

scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj)


def srgb(hex_colour):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return tuple(channel(int(hex_colour[i:i + 2], 16)) for i in (1, 3, 5)) + (1.0,)


def material(name, colour, rough=0.5, metal=0.0, emit=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = srgb(colour)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = srgb(colour)
        bsdf.inputs["Emission Strength"].default_value = emit
    return mat


def glass_body():
    """Skin that is clear face-on and denser at grazing angles, so the inside stays readable."""
    mat = material("body", "#6F8683", rough=0.38)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    weight = nodes.new("ShaderNodeLayerWeight")
    weight.inputs["Blend"].default_value = 0.42
    ramp = nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.1
    ramp.inputs["From Max"].default_value = 1.0
    ramp.inputs["To Min"].default_value = 0.07
    ramp.inputs["To Max"].default_value = 0.8
    links.new(weight.outputs["Facing"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], nodes["Principled BSDF"].inputs["Alpha"])
    return mat


def hatched_screen():
    """The controller's screen shows the hatched Unknown state used across the product."""
    mat = material("screen", "#C9780A", rough=0.3)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coord = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    wave.bands_direction = "DIAGONAL"
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = 42.0
    wave.inputs["Distortion"].default_value = 0.0
    steps = nodes.new("ShaderNodeValToRGB")
    steps.color_ramp.interpolation = "CONSTANT"
    steps.color_ramp.elements[0].color = srgb("#F0D29F")
    steps.color_ramp.elements[1].position = 0.5
    steps.color_ramp.elements[1].color = srgb("#C9780A")
    links.new(coord.outputs["Object"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], steps.inputs["Fac"])
    bsdf = nodes["Principled BSDF"]
    links.new(steps.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(steps.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.1
    return mat


def add_mesh(name, bm, mat, smooth=True):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True
    return obj


def sphere(location, radius, mat, scale=(1, 1, 1), name="sphere", segments=24, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    obj = add_mesh(name, bm, mat)
    obj.location = location
    obj.scale = scale
    return obj


def rounded_box(name, size, location, mat, rotation=(0, 0, 0), bevel=0.3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    obj = add_mesh(name, bm, mat, smooth=False)
    obj.scale = size
    obj.location = location
    obj.rotation_euler = rotation
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = min(size) * bevel
    mod.segments = 5
    mod.limit_method = "NONE"
    mod.use_clamp_overlap = True
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    obj.select_set(False)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def cylinder(name, radius, depth, location, mat, rotation=(0, 0, 0), bevel=0.0, segments=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=depth)
    obj = add_mesh(name, bm, mat, smooth=False)
    obj.location = location
    obj.rotation_euler = rotation
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 4
    for poly in obj.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    return obj


def tube(name, points, radius, mat):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, co in zip(spline.bezier_points, points):
        point.co = co
        point.handle_left_type = point.handle_right_type = "AUTO"
    curve.materials.append(mat)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return obj


# Mannequin: chains of spheres merged into one skin by a voxel remesh.
LIMBS = [
    [(0.095, 0.0, 0.93, 0.095), (0.105, -0.01, 0.50, 0.055), (0.11, 0.01, 0.09, 0.036), (0.12, -0.15, 0.035, 0.03)],
    [(-0.095, 0.0, 0.93, 0.095), (-0.105, -0.01, 0.50, 0.055), (-0.11, 0.01, 0.09, 0.036), (-0.12, -0.15, 0.035, 0.03)],
    [(0.07, 0.0, 0.95, 0.098), (0.06, 0.0, 1.10, 0.092), (0.085, 0.0, 1.30, 0.108), (0.13, 0.0, 1.42, 0.058)],
    [(-0.07, 0.0, 0.95, 0.098), (-0.06, 0.0, 1.10, 0.092), (-0.085, 0.0, 1.30, 0.108), (-0.13, 0.0, 1.42, 0.058)],
    [(0.0, 0.0, 1.44, 0.052), (0.0, -0.005, 1.54, 0.045)],
    [(0.0, -0.005, 1.60, 0.082), (0.0, -0.015, 1.66, 0.09)],
    [(0.19, 0.0, 1.42, 0.05), (0.23, 0.01, 1.14, 0.04), (0.25, -0.04, 0.90, 0.031), (0.255, -0.06, 0.82, 0.034)],
    [(-0.19, 0.0, 1.42, 0.05), (-0.25, 0.03, 1.15, 0.04), (-0.31, -0.19, 1.11, 0.031), (-0.335, -0.26, 1.11, 0.034)],
]
skin = bmesh.new()
for limb in LIMBS:
    for (x0, y0, z0, r0), (x1, y1, z1, r1) in zip(limb, limb[1:] or limb):
        length = math.dist((x0, y0, z0), (x1, y1, z1))
        steps = max(1, int(length / (min(r0, r1) * 0.45)))
        for i in range(steps + 1):
            f = i / steps
            r = r0 + (r1 - r0) * f
            centre = Vector((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, z0 + (z1 - z0) * f))
            part = bmesh.ops.create_icosphere(skin, subdivisions=2, radius=r)
            bmesh.ops.translate(skin, verts=part["verts"], vec=centre)
body = add_mesh("body", skin, glass_body())
remesh = body.modifiers.new("skin", "REMESH")
remesh.mode = "VOXEL"
remesh.voxel_size = 0.011
remesh.use_smooth_shade = True
relax = body.modifiers.new("relax", "SMOOTH")
relax.factor = 1.0
relax.iterations = 24

# Skeleton, only as much as is needed to find the spine and the pelvis.
bone = material("bone", "#D8CFB4", rough=0.62)
disc = material("disc", "#8FA3A0", rough=0.7)
SPINE_BOTTOM, SPINE_TOP, VERTEBRAE = 0.94, 1.50, 22
def spine_y(z):
    f = (z - SPINE_BOTTOM) / (SPINE_TOP - SPINE_BOTTOM)
    return 0.045 + 0.018 * math.sin(f * math.tau * 0.9 + 0.6)
for i in range(VERTEBRAE):
    z = SPINE_BOTTOM + (SPINE_TOP - SPINE_BOTTOM) * i / (VERTEBRAE - 1)
    radius = 0.024 - 0.011 * i / (VERTEBRAE - 1)
    cylinder(f"vertebra{i}", radius, 0.017, (0, spine_y(z), z), bone, bevel=0.004, segments=24)
    if i < VERTEBRAE - 1:
        cylinder(f"disc{i}", radius * 0.86, 0.012, (0, spine_y(z), z + 0.0135), disc, segments=20)
    # Short spinous process facing the viewer, which makes the column read as a spine.
    sphere((0, spine_y(z) + radius + 0.009, z), 0.009, bone, scale=(0.6, 1.6, 0.7), name="process", segments=12, rings=8)
sphere((0, 0.052, 0.905), 0.038, bone, scale=(0.82, 0.36, 1.0), name="sacrum")
sphere((0.092, 0.02, 0.985), 0.07, bone, scale=(0.95, 0.2, 0.72), name="pelvis_l")
sphere((-0.092, 0.02, 0.985), 0.07, bone, scale=(0.95, 0.2, 0.72), name="pelvis_r")

# Devices. Generic shapes, sized for legibility and not to scale.
titanium = material("titanium", "#B9C1C3", rough=0.32, metal=1.0)
amber = material("lead", "#C9780A", rough=0.4)
graphite = material("graphite", "#1D2327", rough=0.45)
teal_light = material("teal_light", "#1C7C6B", rough=0.4, emit=3.0)
amber_light = material("amber_light", "#C9780A", rough=0.4, emit=3.0)

IMPLANT = (-0.1, 0.082, 0.945)
cylinder("implant", 0.042, 0.013, IMPLANT, titanium, rotation=(math.pi / 2, 0, 0), bevel=0.0045)

PADDLE_Z = 1.17
paddle_y = spine_y(PADDLE_Z) + 0.044
rounded_box("paddle", (0.024, 0.004, 0.085), (0, paddle_y, PADDLE_Z), amber, bevel=0.45)
for row in range(4):
    for side in (-0.006, 0.006):
        sphere((side, paddle_y + 0.002, PADDLE_Z - 0.03 + row * 0.02), 0.0034, titanium, scale=(1, 0.4, 1), name="contact", segments=12, rings=8)
tube("lead", [(0, paddle_y, PADDLE_Z - 0.04), (-0.006, paddle_y + 0.008, 1.08), (-0.055, 0.082, 1.01),
              (IMPLANT[0] + 0.004, IMPLANT[1] + 0.001, IMPLANT[2] + 0.04)], 0.0026, amber)

# A closed strap around the waist, which carries the communicator.
strap_points = [(0.156 * math.cos(i * math.tau / 12), 0.1 * math.sin(i * math.tau / 12), 1.04) for i in range(12)]
strap = tube("belt", strap_points, 0.0075, graphite)
strap.data.splines[0].use_cyclic_u = True
COMMUNICATOR = (-0.112, 0.092, 1.04)
rounded_box("communicator", (0.086, 0.028, 0.06), COMMUNICATOR, graphite, rotation=(0, 0, math.radians(-28)), bevel=0.42)
sphere((COMMUNICATOR[0] - 0.012, COMMUNICATOR[1] + 0.015, COMMUNICATOR[2] + 0.014), 0.0048, teal_light, name="communicator_led", segments=12, rings=8)

CONTROLLER = (-0.36, -0.285, 1.145)
TILT = (math.radians(-52), 0, math.radians(-14))
rounded_box("controller", (0.17, 0.112, 0.012), CONTROLLER, graphite, rotation=TILT, bevel=0.42)
normal = Vector((0, 0, 1))
normal.rotate(bpy.data.objects["controller"].rotation_euler)
screen = rounded_box("screen", (0.148, 0.09, 0.0014), Vector(CONTROLLER) + normal * 0.0068, hatched_screen(), rotation=TILT, bevel=0.3)
screen.modifiers.clear()


def beads(start, end, lift, mat, count):
    """A row of dots for a radio link, arcing between two devices."""
    start, end = Vector(start), Vector(end)
    for i in range(1, count):
        f = i / count
        point = start.lerp(end, f) + Vector(lift) * (4 * f * (1 - f))
        sphere(point, 0.0058, mat, name="signal", segments=12, rings=8)


beads(CONTROLLER, Vector(COMMUNICATOR) + Vector((0, 0.02, 0)), (-0.02, 0.2, 0.17), teal_light, 22)
beads(COMMUNICATOR, IMPLANT, (-0.045, 0.03, 0.0), amber_light, 6)

# Light and camera.
def area(location, size, power, colour="#FFFFFF"):
    data = bpy.data.lights.new("area", "AREA")
    data.size = size
    data.energy = power
    data.color = srgb(colour)[:3]
    obj = bpy.data.objects.new("area", data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    track = obj.constraints.new("TRACK_TO")
    track.target = target
    return obj


target = bpy.data.objects.new("target", None)
bpy.context.collection.objects.link(target)
target.location = (-0.14, 0.0, 1.13)
area((-2.2, 2.6, 3.0), 2.6, 120)
area((2.4, 1.5, 1.6), 2.0, 40, "#DCEBF0")
area((0.2, -2.8, 2.0), 2.4, 40, "#FFF1DD")

cam_data = bpy.data.cameras.new("camera")
cam_data.lens = 58
cam_data.sensor_fit = "VERTICAL"
cam_data.sensor_height = 27.0
camera = bpy.data.objects.new("camera", cam_data)
bpy.context.collection.objects.link(camera)
camera.location = (-1.55, 2.5, 1.32)
track = camera.constraints.new("TRACK_TO")
track.target = target
scene.camera = camera

world = bpy.data.worlds.new("world")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = srgb("#F3F6F5")
world.node_tree.nodes["Background"].inputs[1].default_value = 0.45
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.seed = 20261102
scene.cycles.use_denoising = True
scene.cycles.transparent_max_bounces = 24
scene.render.film_transparent = True
scene.render.resolution_x = WIDTH
scene.render.resolution_y = HEIGHT
scene.view_settings.view_transform = "Standard"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = str(OUT / "system_scene.png")

bpy.context.view_layer.update()
anchors = {}
for key, point in {"controller": CONTROLLER, "communicator": COMMUNICATOR, "implant": IMPLANT,
                   "lead": (0, paddle_y, PADDLE_Z)}.items():
    co = world_to_camera_view(scene, camera, Vector(point))
    anchors[key] = {"x": round(co.x * 100, 1), "y": round((1 - co.y) * 100, 1)}
(OUT / "system_scene.json").write_text(json.dumps(anchors, indent=2))

bpy.ops.render.render(write_still=True)
print("ANCHORS", json.dumps(anchors))
