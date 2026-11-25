shader_type canvas_item;
render_mode unshaded;

// TEXTURE = cell grid (RG8): r = material id, g = data (bit7 stamp, bits0-6 shade/life)
uniform sampler2D cells : filter_nearest; // same as TEXTURE (helpers cannot read TEXTURE)
uniform sampler2D palette : filter_nearest; // 256x4 material table
uniform vec4 bg_dark : source_color = vec4(0.05, 0.04, 0.07, 1.0);
uniform vec4 bg_light : source_color = vec4(0.13, 0.11, 0.16, 1.0);
uniform float bg_stars = 0.0;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float a = hash12(i);
	float b = hash12(i + vec2(1.0, 0.0));
	float c = hash12(i + vec2(0.0, 1.0));
	float d = hash12(i + vec2(1.0, 1.0));
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

int mat_at(ivec2 p, ivec2 sz) {
	ivec2 q = clamp(p, ivec2(0), sz - ivec2(1));
	return int(texelFetch(cells, q, 0).r * 255.0 + 0.5);
}

bool solid_at(ivec2 p, ivec2 sz) {
	int m = mat_at(p, sz);
	return texelFetch(palette, ivec2(m, 3), 0).r > 0.5;
}

vec3 background(vec2 wp, ivec2 p, ivec2 sz) {
	float n = vnoise(wp * 0.03) * 0.55 + vnoise(wp * 0.09 + 17.0) * 0.3 + vnoise(wp * 0.35) * 0.15;
	n = floor(n * 7.0) / 7.0;
	vec3 c = mix(bg_dark.rgb, bg_light.rgb, n);
	// Ambient occlusion next to solid walls
	float occ = 0.0;
	if (solid_at(p + ivec2(0, -1), sz)) occ += 0.22;
	if (solid_at(p + ivec2(0, 1), sz)) occ += 0.22;
	if (solid_at(p + ivec2(-1, 0), sz)) occ += 0.22;
	if (solid_at(p + ivec2(1, 0), sz)) occ += 0.22;
	if (solid_at(p + ivec2(0, -3), sz)) occ += 0.1;
	if (solid_at(p + ivec2(0, 3), sz)) occ += 0.1;
	if (solid_at(p + ivec2(-3, 0), sz)) occ += 0.1;
	if (solid_at(p + ivec2(3, 0), sz)) occ += 0.1;
	c *= 1.0 - min(occ, 0.75) * 0.6;
	if (bg_stars > 0.5) {
		float s = hash12(floor(wp));
		if (s > 0.994) {
			float tw = 0.5 + 0.5 * sin(TIME * 2.0 + s * 300.0);
			c = mix(c, vec3(0.85, 0.8, 1.0), 0.75 * tw);
		}
	}
	return c;
}

void fragment() {
	ivec2 sz = textureSize(cells, 0);
	ivec2 p = ivec2(floor(UV * vec2(sz)));
	p = clamp(p, ivec2(0), sz - ivec2(1));
	vec4 t = texelFetch(cells, p, 0);
	int m = int(t.r * 255.0 + 0.5);
	int d = int(t.g * 255.0 + 0.5) & 127;
	vec2 wp = vec2(p);
	vec3 bg = background(wp, p, sz);
	vec3 outc = bg;
	if (m != 0) {
		vec4 c0 = texelFetch(palette, ivec2(m, 0), 0);
		vec4 c1 = texelFetch(palette, ivec2(m, 1), 0);
		vec4 pr = texelFetch(palette, ivec2(m, 2), 0);
		int fx = int(pr.g * 255.0 + 0.5);
		float v = float(d) / 127.0;
		vec3 col = mix(c0.rgb, c1.rgb, v);
		float a = c0.a;
		if (fx == 1) {
			// liquid: gentle moving shimmer
			float w = sin(TIME * 2.2 + wp.x * 0.33 + wp.y * 0.55) * 0.5 + 0.5;
			col = mix(c0.rgb, c1.rgb, clamp(v * 0.45 + w * 0.55, 0.0, 1.0));
		} else if (fx == 2) {
			// fire: colour from remaining life
			float fl = hash12(wp + floor(TIME * 24.0) * 3.1);
			float l = clamp(v * 1.5 + fl * 0.3 - 0.1, 0.0, 1.0);
			col = mix(vec3(0.5, 0.06, 0.02), vec3(1.0, 0.42, 0.07), smoothstep(0.0, 0.45, l));
			col = mix(col, vec3(1.0, 0.94, 0.62), smoothstep(0.55, 1.0, l));
			a = clamp(0.5 + l, 0.0, 1.0);
		} else if (fx == 3) {
			// lava: slow churning glow
			float n = vnoise(wp * 0.12 + vec2(TIME * 0.35, TIME * 0.2)) * 0.7 + hash12(wp) * 0.3;
			col = mix(c0.rgb, c1.rgb, smoothstep(0.25, 0.85, n));
		} else if (fx == 4) {
			// shimmer / sparkle
			float s = hash12(wp + floor(TIME * 3.0) * 7.0);
			if (s > 0.985) col = mix(col, vec3(1.0), 0.6);
		} else if (fx == 5) {
			// gas: fade out with life
			a = c0.a * clamp(v * 2.2, 0.0, 1.0);
		} else if (fx == 6) {
			// ember: flickering burning solid
			float fl = hash12(wp + floor(TIME * 12.0) * 5.3);
			col = mix(c0.rgb, c1.rgb, fl * fl);
		}
		float edge = pr.b;
		if (edge > 0.0) {
			bool su = solid_at(p + ivec2(0, -1), sz);
			bool sd = solid_at(p + ivec2(0, 1), sz);
			int mu = mat_at(p + ivec2(0, -1), sz);
			if (!su && mu != m) {
				col *= 1.0 + 0.32 * edge;
			} else if (!sd) {
				col *= 1.0 - 0.35 * edge;
			} else {
				bool sl = solid_at(p + ivec2(-1, 0), sz);
				bool sr = solid_at(p + ivec2(1, 0), sz);
				if (!sl) col *= 1.0 + 0.12 * edge;
				if (!sr) col *= 1.0 - 0.15 * edge;
			}
			// Depth: solid interior far from open space is darker (rim-lit look).
			if (edge > 0.4) {
				bool open_near = !solid_at(p + ivec2(3, 0), sz) || !solid_at(p + ivec2(-3, 0), sz)
					|| !solid_at(p + ivec2(0, 3), sz) || !solid_at(p + ivec2(0, -3), sz);
				if (!open_near) {
					bool open_mid = !solid_at(p + ivec2(6, 4), sz) || !solid_at(p + ivec2(-6, -4), sz)
						|| !solid_at(p + ivec2(-4, 6), sz) || !solid_at(p + ivec2(4, -6), sz);
					col *= open_mid ? 0.86 : 0.72;
				}
			}
		}
		outc = mix(bg, col, a);
	}
	COLOR = vec4(outc, 1.0);
}
