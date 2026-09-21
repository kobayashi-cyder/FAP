#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#if defined(_WIN32)
#define FAP_EXPORT __declspec(dllexport)
#else
#define FAP_EXPORT __attribute__((visibility("default")))
#endif

static void normalize3(double *x, double *y, double *z) {
    double len = sqrt((*x)*(*x) + (*y)*(*y) + (*z)*(*z));
    if (len <= 1e-12) {
        *x = 0.0;
        *y = 1.0;
        *z = 0.0;
        return;
    }
    *x /= len;
    *y /= len;
    *z /= len;
}

static int is_ground(uint8_t r, uint8_t g, uint8_t b) {
    return r == 204 && g == 207 && b == 203;
}

static double cat_noise(double x, double y, double z) {
    return sin(x * 4.31 + sin(y * 2.17) * 1.9 + z * 3.73);
}

FAP_EXPORT int fap_prepare_geometry(
    const double *positions,
    int vertex_count,
    const int32_t *faces,
    const uint8_t *colors,
    int face_count,
    int width,
    int height,
    double yaw_deg,
    double pitch_deg,
    int tile_size,
    double *view_out,
    double *projected_out,
    double *normals_out,
    int32_t *tiles_out,
    int max_tiles
) {
    if (!positions || !faces || !colors || !view_out || !projected_out ||
        !normals_out || !tiles_out) return -1;
    if (vertex_count <= 0 || face_count <= 0 || width <= 0 || height <= 0 ||
        tile_size <= 0 || max_tiles <= 0) return -2;

    const double pi = 3.14159265358979323846;
    double yaw = yaw_deg * pi / 180.0;
    double pitch = pitch_deg * pi / 180.0;
    double cy = cos(yaw), sy = sin(yaw);
    double cp = cos(pitch), sp = sin(pitch);
    double focal = (double)(width < height ? width : height) * 1.40;
    double camera_distance = 7.0;

    for (int i = 0; i < vertex_count; ++i) {
        double qx = positions[i*3+0];
        double qy = positions[i*3+1] - 0.10;
        double qz = positions[i*3+2];

        double x1 = cy * qx + sy * qz;
        double z1 = -sy * qx + cy * qz;
        double y2 = cp * qy - sp * z1;
        double z2 = sp * qy + cp * z1;

        view_out[i*3+0] = x1;
        view_out[i*3+1] = y2;
        view_out[i*3+2] = z2;

        double zc = camera_distance + z2;
        if (zc < 0.25) zc = 0.25;
        projected_out[i*3+0] = (double)width * 0.5 + focal * x1 / zc;
        projected_out[i*3+1] = (double)height * 0.48 - focal * y2 / zc;
        projected_out[i*3+2] = zc;

        normals_out[i*3+0] = 0.0;
        normals_out[i*3+1] = 0.0;
        normals_out[i*3+2] = 0.0;
    }

    int tiles_x = (width + tile_size - 1) / tile_size;
    int tiles_y = (height + tile_size - 1) / tile_size;
    int total_tiles = tiles_x * tiles_y;
    uint8_t *bitmap = (uint8_t*)calloc((size_t)total_tiles, sizeof(uint8_t));
    if (!bitmap) return -3;

    for (int fi = 0; fi < face_count; ++fi) {
        int ia = faces[fi*3+0];
        int ib = faces[fi*3+1];
        int ic = faces[fi*3+2];
        if (ia < 0 || ib < 0 || ic < 0 ||
            ia >= vertex_count || ib >= vertex_count || ic >= vertex_count) {
            continue;
        }

        uint8_t r = colors[fi*3+0], g = colors[fi*3+1], b = colors[fi*3+2];
        if (is_ground(r,g,b)) continue;

        const double *a = view_out + ia*3;
        const double *bb = view_out + ib*3;
        const double *c = view_out + ic*3;
        double ux = bb[0] - a[0], uy = bb[1] - a[1], uz = bb[2] - a[2];
        double vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
        double nx = uy*vz - uz*vy;
        double ny = uz*vx - ux*vz;
        double nz = ux*vy - uy*vx;
        double nlen2 = nx*nx + ny*ny + nz*nz;
        if (nlen2 > 1e-24) {
            normals_out[ia*3+0] += nx;
            normals_out[ia*3+1] += ny;
            normals_out[ia*3+2] += nz;
            normals_out[ib*3+0] += nx;
            normals_out[ib*3+1] += ny;
            normals_out[ib*3+2] += nz;
            normals_out[ic*3+0] += nx;
            normals_out[ic*3+1] += ny;
            normals_out[ic*3+2] += nz;
        }

        const double *pa = projected_out + ia*3;
        const double *pb = projected_out + ib*3;
        const double *pc = projected_out + ic*3;
        int min_x = (int)floor(fmin(pa[0], fmin(pb[0], pc[0]))) - 2;
        int max_x = (int)ceil (fmax(pa[0], fmax(pb[0], pc[0]))) + 2;
        int min_y = (int)floor(fmin(pa[1], fmin(pb[1], pc[1]))) - 2;
        int max_y = (int)ceil (fmax(pa[1], fmax(pb[1], pc[1]))) + 2;
        if (min_x < 0) min_x = 0;
        if (min_y < 0) min_y = 0;
        if (max_x >= width) max_x = width - 1;
        if (max_y >= height) max_y = height - 1;
        if (min_x > max_x || min_y > max_y) continue;

        int tx0 = min_x / tile_size, tx1 = max_x / tile_size;
        int ty0 = min_y / tile_size, ty1 = max_y / tile_size;
        for (int ty = ty0; ty <= ty1; ++ty) {
            for (int tx = tx0; tx <= tx1; ++tx) {
                if (tx >= 0 && tx < tiles_x && ty >= 0 && ty < tiles_y) {
                    bitmap[ty * tiles_x + tx] = 1;
                }
            }
        }
    }

    for (int i = 0; i < vertex_count; ++i) {
        double nx = normals_out[i*3+0];
        double ny = normals_out[i*3+1];
        double nz = normals_out[i*3+2];
        normalize3(&nx,&ny,&nz);
        normals_out[i*3+0] = nx;
        normals_out[i*3+1] = ny;
        normals_out[i*3+2] = nz;
    }

    int count = 0;
    for (int ty = 0; ty < tiles_y && count < max_tiles; ++ty) {
        for (int tx = 0; tx < tiles_x && count < max_tiles; ++tx) {
            if (bitmap[ty * tiles_x + tx]) {
                tiles_out[count*2+0] = tx;
                tiles_out[count*2+1] = ty;
                count++;
            }
        }
    }
    free(bitmap);
    return count;
}

FAP_EXPORT int fap_apply_cat_pattern(
    const double *vertices,
    int vertex_count,
    const int32_t *faces,
    const uint8_t *colors_in,
    int face_count,
    int coat_code,
    int face_code,
    uint8_t *colors_out
) {
    if (!vertices || !faces || !colors_in || !colors_out) return -1;
    if (vertex_count <= 0 || face_count <= 0) return -2;

    for (int fi = 0; fi < face_count; ++fi) {
        int ia = faces[fi*3+0], ib = faces[fi*3+1], ic = faces[fi*3+2];
        uint8_t r = colors_in[fi*3+0];
        uint8_t g = colors_in[fi*3+1];
        uint8_t b = colors_in[fi*3+2];
        uint8_t orr = r, og = g, ob = b;

        if (ia >= 0 && ib >= 0 && ic >= 0 &&
            ia < vertex_count && ib < vertex_count && ic < vertex_count &&
            ((int)r + (int)g + (int)b) > 120) {
            double x = (
                vertices[ia*3+0] + vertices[ib*3+0] + vertices[ic*3+0]
            ) / 3.0;
            double y = (
                vertices[ia*3+1] + vertices[ib*3+1] + vertices[ic*3+1]
            ) / 3.0;
            double z = (
                vertices[ia*3+2] + vertices[ib*3+2] + vertices[ic*3+2]
            ) / 3.0;

            if (coat_code == 1) {
                double n1 = cat_noise(x*0.75, y*0.65, z*0.7);
                double n2 = cat_noise(x*0.52 + 1.2, y*0.80, z*0.55 - 0.7);
                if (n1 > 0.38) { orr=48; og=45; ob=42; }
                else if (n2 > 0.28) { orr=195; og=109; ob=46; }
                else { orr=232; og=228; ob=216; }
            } else if (coat_code == 2) {
                double stripe = sin(x*12.0 + y*7.0);
                if (stripe > 0.45) { orr=70; og=63; ob=55; }
                else { orr=148; og=132; ob=110; }
            } else if (coat_code == 3) {
                double stripe = sin(x*12.0 + y*7.0);
                if (stripe > 0.45) { orr=63; og=67; ob=70; }
                else { orr=184; og=186; ob=184; }
            } else if (coat_code == 4) {
                double stripe = sin(x*12.0 + y*7.0);
                if (stripe > 0.45) { orr=154; og=74; ob=28; }
                else { orr=222; og=137; ob=67; }
            } else if (coat_code == 5) {
                double n = cat_noise(x*0.9, y*0.85, z*0.8);
                if (n > 0.0) { orr=45; og=42; ob=39; }
                else { orr=180; og=82; ob=34; }
            }

            if (face_code == 1) {
                int on_head = x > 0.22 && y > -1.08 && z < -0.08;
                if (on_head) {
                    double forehead_y = (y + 1.08) / 0.52;
                    if (forehead_y < 0.0) forehead_y = 0.0;
                    if (forehead_y > 1.0) forehead_y = 1.0;
                    double half_width = 0.035 + (1.0 - forehead_y) * 0.16;
                    if (fabs(x - 0.49) < half_width) {
                        orr=238; og=235; ob=225;
                    }
                }
            }
        }

        colors_out[fi*3+0] = orr;
        colors_out[fi*3+1] = og;
        colors_out[fi*3+2] = ob;
    }
    return face_count;
}

static void transform_point(const double *m, double x, double y, double z,
                            double *ox, double *oy, double *oz) {
    *ox = m[0]*x + m[1]*y + m[2]*z + m[3];
    *oy = m[4]*x + m[5]*y + m[6]*z + m[7];
    *oz = m[8]*x + m[9]*y + m[10]*z + m[11];
}

FAP_EXPORT int fap_lbs_sparse(
    const double *bind_positions,
    int vertex_count,
    const int32_t *bone_ids,
    const double *weights,
    const double *skin_matrices,
    int bone_count,
    const uint8_t *affected_bones,
    const double *previous_positions,
    double *out_positions
) {
    if (!bind_positions || !bone_ids || !weights || !skin_matrices ||
        !affected_bones || !out_positions) return -1;
    if (vertex_count <= 0 || bone_count <= 0) return -2;

    int updated = 0;
    for (int vi = 0; vi < vertex_count; ++vi) {
        int needs_update = previous_positions == NULL ? 1 : 0;
        int valid = 0;
        double total = 0.0;
        for (int j = 0; j < 4; ++j) {
            int bi = bone_ids[vi*4+j];
            double w = weights[vi*4+j];
            if (bi >= 0 && bi < bone_count && w > 0.0) {
                valid++;
                total += w;
                if (affected_bones[bi]) needs_update = 1;
            }
        }

        if (!needs_update && previous_positions != NULL) {
            out_positions[vi*3+0] = previous_positions[vi*3+0];
            out_positions[vi*3+1] = previous_positions[vi*3+1];
            out_positions[vi*3+2] = previous_positions[vi*3+2];
            continue;
        }

        double bx = bind_positions[vi*3+0];
        double by = bind_positions[vi*3+1];
        double bz = bind_positions[vi*3+2];
        if (valid == 0 || total <= 1e-12) {
            out_positions[vi*3+0] = bx;
            out_positions[vi*3+1] = by;
            out_positions[vi*3+2] = bz;
            updated++;
            continue;
        }

        double rx=0.0, ry=0.0, rz=0.0;
        for (int j = 0; j < 4; ++j) {
            int bi = bone_ids[vi*4+j];
            double w = weights[vi*4+j];
            if (bi < 0 || bi >= bone_count || w <= 0.0) continue;
            double px, py, pz;
            transform_point(
                skin_matrices + bi*16,
                bx, by, bz,
                &px, &py, &pz
            );
            double wn = w / total;
            rx += px * wn;
            ry += py * wn;
            rz += pz * wn;
        }
        out_positions[vi*3+0] = rx;
        out_positions[vi*3+1] = ry;
        out_positions[vi*3+2] = rz;
        updated++;
    }
    return updated;
}

FAP_EXPORT const char* fap_native_geometry_version(void) {
    return "v87.39-c99-1";
}
