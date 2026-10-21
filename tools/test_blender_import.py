import os, sys, site, io, struct, math
sys.path.append(site.getusersitepackages())

import bpy
from mathutils import Vector, Quaternion, Euler
import UnityPy
from PIL import Image

def unity_pos_to_blender(pos_u):
    return Vector((pos_u[0], pos_u[2], pos_u[1]))

def unity_rot_euler_to_blender(rot_u):
    rx, ry, rz = rot_u
    e = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), 'ZXY')
    q = e.to_quaternion()
    qb = Quaternion((q.w, q.x, q.z, q.y))
    return qb.to_euler('XYZ')

def unity_scale_to_blender(scl_u):
    return Vector((scl_u[0], scl_u[2], scl_u[1]))

print("Transform conversion functions verified.")
