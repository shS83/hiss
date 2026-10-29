#version 330 core
in vec2 uv;
out vec4 color;
uniform sampler2D source;
void main() { color = texture(source, uv); }
