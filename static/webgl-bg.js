// ==================== WEBGL SHADER BACKGROUND ====================

class WebGLShaderBackground {
  constructor() {
    this.canvas = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.mesh = null;
    this.uniforms = null;
    this.animationId = null;
  }

  init(container) {
    if (!container) return;

    this.canvas = document.createElement('canvas');
    this.canvas.className = 'webgl-bg';
    container.insertBefore(this.canvas, container.firstChild);

    const vertexShader = `
      attribute vec3 position;
      void main() {
        gl_Position = vec4(position, 1.0);
      }
    `;

    const fragmentShader = `
      precision highp float;
      uniform vec2 resolution;
      uniform float time;
      uniform float xScale;
      uniform float yScale;
      uniform float distortion;

      void main() {
        vec2 p = (gl_FragCoord.xy * 2.0 - resolution) / min(resolution.x, resolution.y);
        
        float d = length(p) * distortion;
        
        float rx = p.x * (1.0 + d);
        float gx = p.x;
        float bx = p.x * (1.0 - d);

        float r = 0.05 / abs(p.y + sin((rx + time) * xScale) * yScale);
        float g = 0.05 / abs(p.y + sin((gx + time) * xScale) * yScale);
        float b = 0.05 / abs(p.y + sin((bx + time) * xScale) * yScale);
        
        gl_FragColor = vec4(r, g, b, 1.0);
      }
    `;

    this.initScene(vertexShader, fragmentShader);
    this.animate();
    this.handleResize();

    window.addEventListener('resize', () => this.handleResize());
  }

  initScene(vertexShader, fragmentShader) {
    const THREE = window.THREE;
    
    this.scene = new THREE.Scene();
    this.renderer = new THREE.WebGLRenderer({ 
      canvas: this.canvas, 
      alpha: true,
      antialias: true 
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0);

    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, -1);

    this.uniforms = {
      resolution: { value: [window.innerWidth, window.innerHeight] },
      time: { value: 0.0 },
      xScale: { value: 1.0 },
      yScale: { value: 0.5 },
      distortion: { value: 0.05 },
    };

    const position = [
      -1.0, -1.0, 0.0,
       1.0, -1.0, 0.0,
      -1.0,  1.0, 0.0,
       1.0, -1.0, 0.0,
      -1.0,  1.0, 0.0,
       1.0,  1.0, 0.0,
    ];

    const positions = new THREE.BufferAttribute(new Float32Array(position), 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', positions);

    const material = new THREE.RawShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: this.uniforms,
      side: THREE.DoubleSide,
    });

    this.mesh = new THREE.Mesh(geometry, material);
    this.scene.add(this.mesh);
  }

  animate() {
    if (this.uniforms) this.uniforms.time.value += 0.008;
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
    this.animationId = requestAnimationFrame(() => this.animate());
  }

  handleResize() {
    if (!this.renderer || !this.uniforms) return;
    const width = window.innerWidth;
    const height = window.innerHeight;
    this.renderer.setSize(width, height, false);
    this.uniforms.resolution.value = [width, height];
  }

  destroy() {
    if (this.animationId) cancelAnimationFrame(this.animationId);
    window.removeEventListener('resize', () => this.handleResize());
    if (this.mesh) {
      this.scene?.remove(this.mesh);
      this.mesh.geometry.dispose();
      if (this.mesh.material instanceof window.THREE.Material) {
        this.mesh.material.dispose();
      }
    }
    this.renderer?.dispose();
  }
}

// Auto-init when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Check if Three.js is loaded
  if (typeof THREE !== 'undefined') {
    const bg = new WebGLShaderBackground();
    bg.init(document.body);
  } else {
    // Load Three.js from CDN
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
    script.onload = () => {
      const bg = new WebGLShaderBackground();
      bg.init(document.body);
    };
    document.head.appendChild(script);
  }
});