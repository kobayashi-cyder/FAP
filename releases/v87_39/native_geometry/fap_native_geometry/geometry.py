from __future__ import annotations

from dataclasses import dataclass
import ctypes

from fap_human_lbs.core import Face, Mesh, mat_mul

from .loader import doubles, i32, load_native_geometry, native_geometry_status, u8

@dataclass
class PreparedGeometry:
    projected: object
    normals: object
    tiles: object
    tile_rows: list[tuple[int,int]]
    faces: object
    colors: object
    positions: object
    vertex_count: int
    face_count: int

def prepare_geometry(mesh:Mesh, positions, *, width:int,height:int,yaw_deg:float,pitch_deg:float,tile_size:int=32):
    lib=load_native_geometry(True)
    pos=doubles(v for p in positions for v in p)
    faces=i32(v for f in mesh.faces for v in (f.a,f.b,f.c))
    colors=u8(v for f in mesh.faces for v in f.color)
    n=len(mesh.vertices); m=len(mesh.faces)
    view=(ctypes.c_double*(n*3))()
    projected=(ctypes.c_double*(n*3))()
    normals=(ctypes.c_double*(n*3))()
    max_tiles=((width+tile_size-1)//tile_size)*((height+tile_size-1)//tile_size)
    tiles=(ctypes.c_int32*(max_tiles*2))()
    count=int(lib.fap_prepare_geometry(
        pos,n,faces,colors,m,width,height,float(yaw_deg),float(pitch_deg),tile_size,
        view,projected,normals,tiles,max_tiles,
    ))
    if count<0: raise RuntimeError(f"native prepare failed: {count}")
    rows=[(int(tiles[i*2]),int(tiles[i*2+1])) for i in range(count)]
    return PreparedGeometry(projected,normals,tiles,rows,faces,colors,pos,n,m)

_COAT={"calico":1,"tabby":2,"silver_tabby":3,"orange_tabby":4,"tortoiseshell":5}
_FACE={"hachiware":1}

def native_cat_pattern(mesh:Mesh, attrs:dict[str,str], fallback=None):
    coat=attrs.get("coat_pattern")
    face=attrs.get("face_pattern")
    if not coat and not face:
        return mesh,{"coat_pattern_applied":None,"face_pattern_applied":None}
    lib=load_native_geometry(False)
    if lib is None:
        if fallback is None: raise RuntimeError("native cat pattern unavailable")
        return fallback(mesh,attrs)
    verts=doubles(v for vertex in mesh.vertices for v in vertex.bind_position)
    faces=i32(v for f in mesh.faces for v in (f.a,f.b,f.c))
    colors=u8(v for f in mesh.faces for v in f.color)
    out=(ctypes.c_uint8*(len(mesh.faces)*3))()
    rc=int(lib.fap_apply_cat_pattern(
        verts,len(mesh.vertices),faces,colors,len(mesh.faces),
        _COAT.get(coat,0),_FACE.get(face,0),out,
    ))
    if rc<0: raise RuntimeError(f"native cat pattern failed: {rc}")
    out_mesh=Mesh(vertices=list(mesh.vertices),faces=[
        Face(f.a,f.b,f.c,(int(out[i*3]),int(out[i*3+1]),int(out[i*3+2])))
        for i,f in enumerate(mesh.faces)
    ])
    out_mesh.validate()
    return out_mesh,{"coat_pattern_applied":coat,"face_pattern_applied":face}

class NativeLBSCache:
    def __init__(self):
        self._cache={}

    def _packed_mesh(self, mesh, skeleton):
        key=(id(mesh),id(skeleton),"packed")
        packed=self._cache.get(key)
        if packed is not None: return packed
        bone_names=[b.name for b in skeleton.bones]
        bone_index={name:i for i,name in enumerate(bone_names)}
        bind=doubles(v for vertex in mesh.vertices for v in vertex.bind_position)
        ids=[]; weights=[]
        for vertex in mesh.vertices:
            row=list(vertex.weights)[:4]
            for j in range(4):
                if j<len(row):
                    name,w=row[j]; ids.append(bone_index[name]); weights.append(float(w))
                else:
                    ids.append(-1); weights.append(0.0)
        packed=(bind,i32(ids),doubles(weights),bone_names)
        self._cache[key]=packed
        return packed

    def skin(self, mesh, skeleton, pose):
        lib=load_native_geometry(False)
        if lib is None:
            globals_now=skeleton.global_matrices(pose)
            return [
                skeleton.skin_point_with_globals(v.bind_position,v.weights,globals_now)
                for v in mesh.vertices
            ],{"native_lbs":False,"updated_vertices":len(mesh.vertices)}

        bind,bone_ids,weights,bone_names=self._packed_mesh(mesh,skeleton)
        globals_now=skeleton.global_matrices(pose)
        matrices=[]
        matrix_rows=[]
        for name in bone_names:
            m=mat_mul(globals_now[name],skeleton._inverse_bind[name])
            matrix_rows.append(m); matrices.extend(m)
        mats=doubles(matrices)

        state_key=(id(mesh),id(skeleton),"state")
        prev=self._cache.get(state_key)
        affected=[]
        prev_arr=None
        if prev is None:
            affected=[1]*len(bone_names)
        else:
            prev_mats,prev_positions=prev
            for old,new in zip(prev_mats,matrix_rows):
                affected.append(1 if any(abs(a-b)>1e-12 for a,b in zip(old,new)) else 0)
            prev_arr=doubles(v for p in prev_positions for v in p)
        affected_arr=u8(affected)
        out=(ctypes.c_double*(len(mesh.vertices)*3))()
        rc=int(lib.fap_lbs_sparse(
            bind,len(mesh.vertices),bone_ids,weights,mats,len(bone_names),
            affected_arr,prev_arr,out,
        ))
        if rc<0: raise RuntimeError(f"native lbs failed: {rc}")
        positions=[
            (float(out[i*3]),float(out[i*3+1]),float(out[i*3+2]))
            for i in range(len(mesh.vertices))
        ]
        self._cache[state_key]=(matrix_rows,positions)
        return positions,{
            "native_lbs":True,
            "updated_vertices":rc,
            "total_vertices":len(mesh.vertices),
            "affected_bones":sum(affected),
            "bone_count":len(bone_names),
        }
