shader_type canvas_item;
render_mode blend_mul, unshaded;

// Full-screen darkness + light overlay. Multiplies everything drawn below it.
uniform sampler2D cells : filter_nearest;
uniform sampler2D palette : filter_nearest;
uniform vec2 world_size = vec2(512.0, 512.0);
uniform vec2 cam_origin = vec2(0.0);
uniform vec2 view_size = vec2(480.0, 270.0);
uniform vec3 ambient = vec3(0.2, 0.2, 0.25);
uniform int light_count = 0;
uniform vec3 light_pos[64];   // x, y, radius
uniform vec3 light_col[64];   // rgb * intensity

vec3 emit_at(vec2 wp) {
	ivec2 p = ivec2(floor(wp));
	if (p.x < 0 || p.y < 0 || p.x >= int(world_size.x) || p.y >= int(world_size.y)) {
		return vec3(0.0);
	}
	int m = int(texelFetch(cells, p, 0).r * 255.0 + 0.5);
	float e = texelFetch(palette, ivec2(m, 2), 0).r;
	if (e <= 0.0) {
		return vec3(0.0);
	}
	vec3 c = texelFetch(palette, ivec2(m, 1), 0).rgb;
	return c * e;
}

void fragment() {
	vec2 wp = cam_origin + UV * view_size;
	vec3 light = ambient;
	for (int i = 0; i < light_count; i++) {
		vec3 lp = light_pos[i];
		float dist = length(wp - lp.xy);
		float f = clamp(1.0 - dist / lp.z, 0.0, 1.0);
		light += light_col[i] * (f * f);
	}
	// Glow from emissive cells around this pixel
	vec3 glow = emit_at(wp) * 1.2;
	for (int k = 0; k < 8; k++) {
		float an = float(k) * 0.7853982 + 0.39;
		vec2 o = vec2(cos(an), sin(an));
		glow += emit_at(wp + o * 3.0) * 0.16;
		glow += emit_at(wp + o * 7.0) * 0.09;
		glow += emit_at(wp + o * 13.0) * 0.045;
	}
	light += glow;
	// Quantise slightly for a pixel-art look
	light = floor(min(light, vec3(1.0)) * 24.0 + 0.5) / 24.0;
	COLOR = vec4(light, 1.0);
}
