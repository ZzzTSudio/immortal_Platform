import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const vertexShader = `
attribute vec2 a_pos;
void main() {
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

const fragmentShader = `
precision highp float;
uniform float u_time;
uniform vec2 u_res;
uniform vec2 u_mouse;

#define TAU 6.2831853
#define MAX_ITER 4

vec3 bgDark = vec3(0.06, 0.06, 0.07);
vec3 bgMid = vec3(0.11, 0.11, 0.12);
vec3 sheen = vec3(0.80, 0.78, 0.72);
vec3 warm = vec3(0.85, 0.80, 0.70);
vec3 hot = vec3(0.95, 0.93, 0.88);
vec3 deep = vec3(0.20, 0.18, 0.14);

float hash(vec2 p) {
  p = fract(p * vec2(443.897, 441.423));
  p += dot(p, p + 19.19);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec2 tiltedCylinderField(vec2 p, float t) {
  float angle = t * 0.08;
  float ca = cos(angle);
  float sa = sin(angle);
  p = vec2(ca * p.x + sa * p.y, -sa * p.x + ca * p.y);

  float drift1 = 0.22;
  float drift2 = 0.35;
  float drift3 = 0.13;

  float wave1 = sin(p.y * 0.35 + t * 0.6) * 0.15;
  float wave2 = sin(p.y * 0.18 + t * 0.4) * 0.25;
  float wave3 = sin(p.y * 0.55 + t * 0.8) * 0.10;

  float d1 = abs(p.x + wave1 - drift1);
  float d2 = abs(p.x + wave2 + drift2);
  float d3 = abs(p.x + wave3);

  float longStrip = smoothstep(6.0, 3.5, abs(p.y));

  float brightBands = (0.35 / (1.0 + d1 * d1 * 20.0)
                     + 0.45 / (1.0 + d2 * d2 * 10.0)
                     + 0.30 / (1.0 + d3 * d3 * 30.0)) * longStrip;

  float darkBand = smoothstep(0.3, 0.8, sin(p.y * 0.25 - t * 0.15) * 0.5 + 0.5);

  return vec2(brightBands, darkBand);
}

vec2 flowWarp(vec2 p, float t) {
  vec2 warp = vec2(0.0);
  float amp = 0.18;
  float freq = 0.25;
  for (int i = 0; i < 3; i++) {
    warp.x += amp * sin(p.y * freq + t * 0.15 + float(i) * 1.7 + warp.x);
    warp.y += amp * cos(p.x * freq + t * 0.12 + float(i) * 2.3 + warp.y);
    amp *= 0.5;
    freq *= 1.6;
  }
  return warp;
}

void main() {
  vec2 uv = (gl_FragCoord.xy - u_res * 0.5) / u_res.y;

  vec2 mouseDirs[8];
  mouseDirs[0] = vec2(1.0, 0.0);
  mouseDirs[1] = vec2(-1.0, 0.0);
  mouseDirs[2] = vec2(0.0, 1.0);
  mouseDirs[3] = vec2(0.0, -1.0);
  mouseDirs[4] = vec2(0.707, 0.707);
  mouseDirs[5] = vec2(-0.707, 0.707);
  mouseDirs[6] = vec2(0.707, -0.707);
  mouseDirs[7] = vec2(-0.707, -0.707);

  float mouseIntensity = 0.0;
  for (int i = 0; i < 8; i++) {
    mouseIntensity += 0.15 / (1.0 + length(uv - mouseDirs[i] * 0.25) * 8.0)
                    * sin(u_time * 0.7 + float(i) * 0.78);
  }

  float t = u_time * 0.5;
  vec2 p = uv * 3.0;
  vec2 warp = flowWarp(p, t);
  vec2 wp = p + warp;

  float crispWarp = sin(wp.x * 2.5 + t * 0.3) * sin(wp.y * 2.8 - t * 0.25);
  float veinX = smoothstep(0.85, 1.0, sin(wp.x * 8.0 + wp.y * 3.0 + t * 0.4) * 0.5 + 0.5) * 0.4;
  float veinY = smoothstep(0.9, 1.0, sin(wp.y * 12.0 - t * 0.35 + wp.x * 2.0) * 0.5 + 0.5) * 0.3;
  float sheenSurface = crispWarp + veinX + veinY;

  float ripple1 = sin(length(p) * 5.0 - t * 1.2);
  float ripple2 = sin(length(p - vec2(1.5, 0.8)) * 7.0 + t * 1.5);
  float ripple3 = sin(length(p + vec2(1.0, 1.2)) * 4.0 + t * 0.9);
  float ripples = smoothstep(-2.0, 2.0, ripple1 + ripple2 + ripple3);
  float hotBand = smoothstep(0.6, 0.9, sin(wp.y * 2.0 + t * 0.2 + wp.x * 0.5) * 0.5 + 0.5);

  vec2 warp2 = flowWarp(p * 1.3 + vec2(t * 0.1, 0.0), t * 0.8);
  float silkBase = vnoise(wp * 1.2 + vec2(t * 0.08, 0.0)) * 0.5 + 0.5;
  float silkDetail = vnoise(wp * 2.5 + vec2(-t * 0.06, t * 0.04) + warp2 * 0.5);
  float silkHighlight = smoothstep(0.4, 0.8, silkBase * 0.6 + silkDetail * 0.4);

  vec2 cylField = tiltedCylinderField(p, t);

  vec3 col = bgDark;
  col = mix(col, bgMid, cylField.y * 0.4);
  col = mix(col, bgMid, silkHighlight * 0.3);

  float shinyLayer = hotBand * silkHighlight + cylField.x * 0.6 + ripples * 0.25;
  col = mix(col, sheen, shinyLayer * 0.45);

  float foldHighlight = smoothstep(0.5, 0.9, silkBase * 0.7 + silkDetail * 0.3 + hotBand * 0.4 + cylField.x * 0.6);
  col = mix(col, warm, foldHighlight * 0.35);

  float coreHot = smoothstep(0.65, 0.95, sheenSurface * 0.3 + hotBand * 0.5 + silkDetail * 0.2 + cylField.x * 0.4 + mouseIntensity * 0.5);
  col = mix(col, hot, coreHot * 0.5);

  float reflectionBand = smoothstep(0.3, 0.7, sin(wp.y * 1.8 + wp.x * 0.6 + t * 0.15 + warp.x * 0.5) * 0.5 + 0.5) * silkHighlight;
  col = mix(col, deep, reflectionBand * 0.4);

  float flowWaves = sin(wp.x * 3.0 + wp.y * 2.5 + t * 0.25) * cos(wp.x * 2.0 - wp.y * 3.5 - t * 0.3);
  float flowMask = smoothstep(0.3, 0.8, flowWaves * 0.5 + 0.5) * silkHighlight;
  col = mix(col, deep, flowMask * 0.3);

  float edgeFade = smoothstep(0.0, 0.6, 1.0 - max(abs(uv.x), abs(uv.y)) * 1.0);
  col *= 0.6 + edgeFade * 0.4;

  float vig = 1.0 - smoothstep(0.3, 1.1, length(uv * vec2(0.9, 1.0)));
  col *= 0.7 + vig * 0.3;

  col = clamp(col, 0.0, 1.0);
  gl_FragColor = vec4(col, 1.0);
}
`;

export default function LiquidChromeBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });
  const mouseTimeoutRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    const camera = new THREE.Camera();

    const geometry = new THREE.BufferGeometry();
    const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
    geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 2));

    const material = new THREE.RawShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        u_time: { value: 0 },
        u_res: { value: new THREE.Vector2(1, 1) },
        u_mouse: { value: new THREE.Vector2(0, 0) }
      }
    });

    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const handleResize = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      renderer.setSize(w, h);
      material.uniforms.u_res.value.set(w, h);
    };
    handleResize();

    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current.targetX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseRef.current.targetY = -((e.clientY / window.innerHeight) * 2 - 1);

      if (mouseTimeoutRef.current) clearTimeout(mouseTimeoutRef.current);
      mouseTimeoutRef.current = window.setTimeout(() => {
        mouseRef.current.targetX = 0;
        mouseRef.current.targetY = 0;
      }, 100);
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);

      const m = mouseRef.current;
      m.x += (m.targetX - m.x) * 0.05;
      m.y += (m.targetY - m.y) * 0.05;

      material.uniforms.u_time.value = performance.now() * 0.001;
      material.uniforms.u_mouse.value.set(m.x, m.y);

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      if (mouseTimeoutRef.current) clearTimeout(mouseTimeoutRef.current);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          zIndex: -1,
          pointerEvents: 'none'
        }}
      />
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          zIndex: -1,
          background: 'rgba(17, 17, 17, 0.85)',
          pointerEvents: 'none'
        }}
      />
    </>
  );
}
