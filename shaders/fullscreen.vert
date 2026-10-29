#version 330 core
out vec2 uv;
void main() {
    // One oversized triangle avoids a diagonal seam across post-process passes.
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
