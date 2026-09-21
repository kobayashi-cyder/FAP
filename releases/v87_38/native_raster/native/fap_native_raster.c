#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>

#if defined(_WIN32)
#define FAP_EXPORT __declspec(dllexport)
#else
#define FAP_EXPORT __attribute__((visibility("default")))
#endif

typedef struct {
    double ambient;
    double diffuse;
    double specular;
    double shininess;
    double micro_noise;
    double warm_shift;
} Material;

static double clamp01(double v) {
    if (v < 0.0) return 0.0;
    if (v > 1.0) return 1.0;
    return v;
}

static uint8_t clamp8(double v) {
    if (v <= 0.0) return 0;
    if (v >= 255.0) return 255;
    return (uint8_t)(v + 0.5);
}

static int is_near(uint8_t r, uint8_t g, uint8_t b, int tr, int tg, int tb, int tolerance) {
    int d = abs((int)r - tr) + abs((int)g - tg) + abs((int)b - tb);
    return d <= tolerance * 3;
}

static Material material_for(uint8_t r, uint8_t g, uint8_t b) {
    Material m;
    if (is_near(r,g,b,214,171,141,32)) {
        m = (Material){0.36,0.72,0.16,22.0,0.018,0.018};
    } else if (is_near(r,g,b,35,32,30,28)) {
        m = (Material){0.26,0.62,0.48,54.0,0.010,0.0};
    } else if (
        is_near(r,g,b,145,101,70,34) ||
        is_near(r,g,b,76,57,48,30) ||
        is_near(r,g,b,190,142,98,34) ||
        is_near(r,g,b,226,218,198,28)
    ) {
        m = (Material){0.34,0.76,0.08,12.0,0.060,0.012};
    } else if (is_near(r,g,b,71,112,158,36)) {
        m = (Material){0.31,0.72,0.05,9.0,0.040,0.0};
    } else if (is_near(r,g,b,57,66,82,34)) {
        m = (Material){0.29,0.68,0.035,8.0,0.035,0.0};
    } else if (is_near(r,g,b,52,48,45,30)) {
        m = (Material){0.24,0.62,0.18,26.0,0.025,0.0};
    } else {
        m = (Material){0.34,0.70,0.08,14.0,0.018,0.0};
    }
    return m;
}

static uint32_t noise_hash(int x, int y, int seed) {
    uint32_t n = (uint32_t)x * 374761393u + (uint32_t)y * 668265263u + (uint32_t)seed * 1442695041u;
    n = (n ^ (n >> 13)) * 1274126177u;
    n ^= n >> 16;
    return n;
}

static double noise01(int x, int y, int seed) {
    return (double)(noise_hash(x,y,seed) & 0xFFFFu) / 65535.0;
}

static double edge(double ax, double ay, double bx, double by, double px, double py) {
    return (px - ax) * (by - ay) - (py - ay) * (bx - ax);
}

static void normalize3(double *x, double *y, double *z) {
    double len = sqrt((*x)*(*x) + (*y)*(*y) + (*z)*(*z));
    if (len <= 1e-15) {
        *x = *y = 0.0;
        *z = 1.0;
        return;
    }
    *x /= len; *y /= len; *z /= len;
}

FAP_EXPORT uint64_t fap_raster_subject(
    uint8_t *rgb,
    float *depth,
    int width,
    int height,
    const double *projected,
    const double *normals,
    const int32_t *faces,
    const uint8_t *colors,
    int face_count
) {
    if (!rgb || !depth || !projected || !normals || !faces || !colors) return 0;
    if (width <= 0 || height <= 0 || face_count <= 0) return 0;

    double lx = -0.48, ly = 0.78, lz = -0.72;
    double fx = 0.66, fy = 0.38, fz = -0.34;
    normalize3(&lx,&ly,&lz);
    normalize3(&fx,&fy,&fz);
    const double vdx = 0.0, vdy = 0.0, vdz = -1.0;
    double hx = lx + vdx, hy = ly + vdy, hz = lz + vdz;
    normalize3(&hx,&hy,&hz);

    uint64_t touched = 0;
    for (int fi = 0; fi < face_count; ++fi) {
        int ia = faces[fi*3+0];
        int ib = faces[fi*3+1];
        int ic = faces[fi*3+2];
        if (ia < 0 || ib < 0 || ic < 0) continue;

        uint8_t cr = colors[fi*3+0], cg = colors[fi*3+1], cb = colors[fi*3+2];
        if (cr == 204 && cg == 207 && cb == 203) continue;

        const double *a = projected + ia*3;
        const double *b = projected + ib*3;
        const double *c = projected + ic*3;
        double area = edge(a[0],a[1],b[0],b[1],c[0],c[1]);
        if (fabs(area) < 1e-8) continue;

        int min_x = (int)floor(fmin(a[0], fmin(b[0], c[0])));
        int max_x = (int)ceil (fmax(a[0], fmax(b[0], c[0])));
        int min_y = (int)floor(fmin(a[1], fmin(b[1], c[1])));
        int max_y = (int)ceil (fmax(a[1], fmax(b[1], c[1])));
        if (min_x < 0) min_x = 0;
        if (min_y < 0) min_y = 0;
        if (max_x >= width) max_x = width - 1;
        if (max_y >= height) max_y = height - 1;
        if (min_x > max_x || min_y > max_y) continue;

        const double *na = normals + ia*3;
        const double *nb = normals + ib*3;
        const double *nc = normals + ic*3;
        Material mat = material_for(cr,cg,cb);
        double inv_area = 1.0 / area;

        for (int py = min_y; py <= max_y; ++py) {
            double yf = (double)py + 0.5;
            for (int px = min_x; px <= max_x; ++px) {
                double xf = (double)px + 0.5;
                double w0 = edge(b[0],b[1],c[0],c[1],xf,yf) * inv_area;
                double w1 = edge(c[0],c[1],a[0],a[1],xf,yf) * inv_area;
                double w2 = 1.0 - w0 - w1;
                if (w0 < -1e-7 || w1 < -1e-7 || w2 < -1e-7) continue;

                double z = w0*a[2] + w1*b[2] + w2*c[2];
                size_t idx = (size_t)py * (size_t)width + (size_t)px;
                if (z >= (double)depth[idx]) continue;

                double nx = na[0]*w0 + nb[0]*w1 + nc[0]*w2;
                double ny = na[1]*w0 + nb[1]*w1 + nc[1]*w2;
                double nz = na[2]*w0 + nb[2]*w1 + nc[2]*w2;
                normalize3(&nx,&ny,&nz);
                double ndv = nx*vdx + ny*vdy + nz*vdz;
                if (ndv < 0.0) {
                    nx = -nx; ny = -ny; nz = -nz;
                    ndv = -ndv;
                }

                double ndl = nx*lx + ny*ly + nz*lz;
                double wrapped = clamp01((ndl + 0.24) / 1.24);
                double fill_term = nx*fx + ny*fy + nz*fz;
                if (fill_term < 0.0) fill_term = 0.0;
                double spec_dot = nx*hx + ny*hy + nz*hz;
                if (spec_dot < 0.0) spec_dot = 0.0;
                double spec = pow(spec_dot, mat.shininess);
                double rim_base = 1.0 - fmax(0.0, ndv);
                if (rim_base < 0.0) rim_base = 0.0;
                double rim = rim_base * rim_base;

                double illum = mat.ambient + mat.diffuse*wrapped + 0.10*fill_term + 0.035*rim;
                double micro = (noise01(px,py,fi+17) - 0.5) * 2.0 * mat.micro_noise;
                illum *= 1.0 + micro;
                double warm = mat.warm_shift * (0.6 + 0.4*wrapped);
                double highlight = 255.0 * mat.specular * spec;

                size_t off = idx * 3u;
                rgb[off+0] = clamp8((double)cr * illum * (1.0 + warm) + highlight);
                rgb[off+1] = clamp8((double)cg * illum + highlight);
                rgb[off+2] = clamp8((double)cb * illum * (1.0 - warm*0.55) + highlight);
                depth[idx] = (float)z;
                touched++;
            }
        }
    }
    return touched;
}

static double luma_at(const uint8_t *src, size_t off) {
    return 0.2126*(double)src[off] + 0.7152*(double)src[off+1] + 0.0722*(double)src[off+2];
}

FAP_EXPORT uint64_t fap_fxaa_tiles(
    uint8_t *rgb,
    int width,
    int height,
    const int32_t *tiles,
    int tile_count,
    int tile_size
) {
    if (!rgb || !tiles || width < 3 || height < 3 || tile_count <= 0 || tile_size <= 0) return 0;
    size_t bytes = (size_t)width * (size_t)height * 3u;
    uint8_t *src = (uint8_t*)malloc(bytes);
    if (!src) return 0;
    memcpy(src, rgb, bytes);

    uint64_t touched = 0;
    for (int ti = 0; ti < tile_count; ++ti) {
        int tx = tiles[ti*2+0], ty = tiles[ti*2+1];
        int x0 = tx * tile_size;
        int y0 = ty * tile_size;
        int x1 = x0 + tile_size;
        int y1 = y0 + tile_size;
        if (x0 < 1) x0 = 1;
        if (y0 < 1) y0 = 1;
        if (x1 > width-1) x1 = width-1;
        if (y1 > height-1) y1 = height-1;

        for (int y=y0; y<y1; ++y) {
            for (int x=x0; x<x1; ++x) {
                size_t off = ((size_t)y*(size_t)width + (size_t)x)*3u;
                size_t left = off-3u, right=off+3u;
                size_t up=off-(size_t)width*3u, down=off+(size_t)width*3u;
                double l0=luma_at(src,off), l1=luma_at(src,left), l2=luma_at(src,right), l3=luma_at(src,up), l4=luma_at(src,down);
                double lo=fmin(l0,fmin(l1,fmin(l2,fmin(l3,l4))));
                double hi=fmax(l0,fmax(l1,fmax(l2,fmax(l3,l4))));
                if (hi-lo < 34.0) continue;
                for (int k=0;k<3;++k) {
                    double neighbor=((double)src[left+k]+src[right+k]+src[up+k]+src[down+k])*0.25;
                    rgb[off+k]=clamp8((double)src[off+k]*0.62 + neighbor*0.38);
                }
                touched++;
            }
        }
    }
    free(src);
    return touched;
}

FAP_EXPORT uint64_t fap_filmic_subject(
    uint8_t *rgb,
    const float *depth,
    int width,
    int height,
    const int32_t *tiles,
    int tile_count,
    int tile_size
) {
    if (!rgb || !depth || !tiles || width<=0 || height<=0 || tile_count<=0 || tile_size<=0) return 0;
    double cx=((double)width-1.0)*0.5;
    double cy=((double)height-1.0)*0.48;
    double invx=1.0/fmax(1.0,(double)width*0.72);
    double invy=1.0/fmax(1.0,(double)height*0.78);
    uint64_t touched=0;

    for (int ti=0; ti<tile_count; ++ti) {
        int tx=tiles[ti*2+0], ty=tiles[ti*2+1];
        int x0=tx*tile_size, y0=ty*tile_size;
        int x1=x0+tile_size, y1=y0+tile_size;
        if (x0<0) x0=0; if (y0<0) y0=0;
        if (x1>width) x1=width; if (y1>height) y1=height;

        for (int y=y0; y<y1; ++y) {
            double dy=((double)y-cy)*invy;
            for (int x=x0; x<x1; ++x) {
                size_t idx=(size_t)y*(size_t)width+(size_t)x;
                if (!(depth[idx] < FLT_MAX*0.5f)) continue;
                double dx=((double)x-cx)*invx;
                double r2=dx*dx+dy*dy;
                double vignette=fmax(0.84,1.0-0.12*r2);
                double grain=(noise01(x,y,991)-0.5)*2.2;
                size_t off=idx*3u;
                for (int k=0;k<3;++k) {
                    double v=(double)rgb[off+k]/255.0;
                    v=fmax(0.0,fmin(1.0,(v*1.055)/(1.0+0.055*v)));
                    v=pow(v,0.94);
                    rgb[off+k]=clamp8(v*255.0*vignette+grain);
                }
                touched++;
            }
        }
    }
    return touched;
}

FAP_EXPORT const char* fap_native_raster_version(void) {
    return "v87.38-c99-1";
}
