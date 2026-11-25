class_name Dimensions
extends RefCounted
## Dimension (biome) definitions. Every level is generated from one of these.

const IDS: Array[String] = ["caves", "fungal", "frost", "forge", "crystal", "void"]


static func get_def(id: String) -> Dictionary:
	match id:
		"fungal":
			return {
				"id": "fungal", "name": "Sienisyvänne", "music": "fungal",
				"size": Vector2i(960, 720), "mode": "caves",
				"base": Mat.DIRT, "cave_freq": 0.0105, "cave_thr": 0.47, "ridge_thr": 0.86,
				"layers": [[Mat.ROCK, 0.012, 0.55], [Mat.FUNGUS, 0.03, 0.74], [Mat.MOSS, 0.04, 0.78], [Mat.SAND, 0.035, 0.82]],
				"coating": Mat.FUNGUS, "coat_depth": 2, "coat_chance": 0.75,
				"ceiling": Mat.FUNGUS, "ceil_chance": 0.25,
				"liquids": {Mat.SLUDGE: 5, Mat.WATER: 3, Mat.ACID: 1}, "pools": 12,
				"structures": {"platforms": 5, "ruins": 1, "kegs": 1, "mushrooms": 9},
				"enemies": {"slime": 5, "bat": 2, "caster": 2, "wisp": 1}, "enemy_base": 11,
				"ambient": Color(0.21, 0.17, 0.29), "bg_dark": Color("0b0711"), "bg_light": Color("23152d"),
				"stars": false, "gravity": 1.0, "tint": Color("b27bd6"), "platform_mat": Mat.WOOD,
			}
		"frost":
			return {
				"id": "frost", "name": "Routaulottuvuus", "music": "frost",
				"size": Vector2i(1024, 640), "mode": "caves",
				"base": Mat.ROCK, "cave_freq": 0.0085, "cave_thr": 0.46, "ridge_thr": 0.87,
				"layers": [[Mat.ICE, 0.011, 0.5], [Mat.SNOW, 0.03, 0.76], [Mat.GRAVEL, 0.05, 0.86]],
				"coating": Mat.SNOW, "coat_depth": 3, "coat_chance": 0.85,
				"ceiling": Mat.ICE, "ceil_chance": 0.35,
				"liquids": {Mat.WATER: 8, Mat.OIL: 1}, "pools": 9,
				"structures": {"platforms": 5, "ruins": 2, "kegs": 1},
				"enemies": {"bat": 3, "slime": 3, "golem": 1, "caster": 1}, "enemy_base": 10,
				"ambient": Color(0.56, 0.60, 0.65), "bg_dark": Color("0d1320"), "bg_light": Color("23314a"),
				"stars": false, "gravity": 1.0, "tint": Color("8fd0ff"), "platform_mat": Mat.WOOD,
			}
		"forge":
			return {
				"id": "forge", "name": "Ahjoulottuvuus", "music": "forge",
				"size": Vector2i(960, 672), "mode": "caves",
				"base": Mat.BASALT, "cave_freq": 0.01, "cave_thr": 0.47, "ridge_thr": 0.85,
				"layers": [[Mat.ROCK, 0.013, 0.6], [Mat.COAL, 0.03, 0.74], [Mat.GRAVEL, 0.05, 0.84], [Mat.GUNPOWDER, 0.06, 0.93]],
				"coating": Mat.ASH, "coat_depth": 1, "coat_chance": 0.4,
				"ceiling": -1, "ceil_chance": 0.0,
				"liquids": {Mat.LAVA: 6, Mat.OIL: 3, Mat.WATER: 1}, "pools": 11,
				"structures": {"platforms": 5, "ruins": 3, "kegs": 3},
				"enemies": {"wisp": 4, "golem": 2, "caster": 2, "slime": 1}, "enemy_base": 11,
				"ambient": Color(0.29, 0.19, 0.15), "bg_dark": Color("130705"), "bg_light": Color("2f140f"),
				"stars": false, "gravity": 1.0, "tint": Color("ff8a5c"), "platform_mat": Mat.METAL,
			}
		"crystal":
			return {
				"id": "crystal", "name": "Kristalliulottuvuus", "music": "crystal",
				"size": Vector2i(960, 704), "mode": "caves",
				"base": Mat.ROCK, "cave_freq": 0.0095, "cave_thr": 0.46, "ridge_thr": 0.86,
				"layers": [[Mat.OBSIDIAN, 0.012, 0.62], [Mat.CRYSTAL, 0.028, 0.7], [Mat.QUARTZ, 0.035, 0.78]],
				"coating": Mat.QUARTZ, "coat_depth": 1, "coat_chance": 0.35,
				"ceiling": Mat.CRYSTAL, "ceil_chance": 0.3,
				"liquids": {Mat.ACID: 5, Mat.AETHER: 2, Mat.WATER: 2}, "pools": 10,
				"structures": {"platforms": 4, "ruins": 2, "kegs": 1, "crystals": 10},
				"enemies": {"caster": 3, "golem": 2, "bat": 2, "slime": 2}, "enemy_base": 11,
				"ambient": Color(0.28, 0.21, 0.40), "bg_dark": Color("0d0918"), "bg_light": Color("251a3c"),
				"stars": false, "gravity": 1.0, "tint": Color("c79bff"), "platform_mat": Mat.METAL,
			}
		"void":
			return {
				"id": "void", "name": "Tyhjyys", "music": "void",
				"size": Vector2i(1120, 640), "mode": "islands",
				"base": Mat.VOIDSTONE, "cave_freq": 0.011, "cave_thr": 0.64, "ridge_thr": 0.0,
				"layers": [[Mat.OBSIDIAN, 0.03, 0.72], [Mat.CRYSTAL, 0.05, 0.86]],
				"coating": Mat.MOSS, "coat_depth": 1, "coat_chance": 0.5,
				"ceiling": -1, "ceil_chance": 0.0,
				"liquids": {Mat.AETHER: 4, Mat.WATER: 1, Mat.ACID: 1}, "pools": 7,
				"structures": {"platforms": 3, "ruins": 2, "kegs": 0},
				"enemies": {"bat": 3, "caster": 3, "wisp": 2}, "enemy_base": 10,
				"ambient": Color(0.24, 0.21, 0.36), "bg_dark": Color("05040b"), "bg_light": Color("120c22"),
				"stars": true, "gravity": 0.6, "tint": Color("7fe0ff"), "platform_mat": Mat.VOIDSTONE,
			}
		_:
			return {
				"id": "caves", "name": "Hämyluolat", "music": "caves",
				"size": Vector2i(960, 672), "mode": "caves",
				"base": Mat.ROCK, "cave_freq": 0.0095, "cave_thr": 0.46, "ridge_thr": 0.86,
				"layers": [[Mat.DIRT, 0.012, 0.6], [Mat.SAND, 0.03, 0.78], [Mat.GRAVEL, 0.045, 0.83], [Mat.COAL, 0.05, 0.9]],
				"coating": Mat.MOSS, "coat_depth": 2, "coat_chance": 0.55,
				"ceiling": -1, "ceil_chance": 0.0,
				"liquids": {Mat.WATER: 7, Mat.OIL: 1, Mat.ACID: 1}, "pools": 10,
				"structures": {"platforms": 6, "ruins": 2, "kegs": 2},
				"enemies": {"slime": 5, "bat": 3, "caster": 1}, "enemy_base": 9,
				"ambient": Color(0.29, 0.31, 0.40), "bg_dark": Color("0c0a11"), "bg_light": Color("221d2b"),
				"stars": false, "gravity": 1.0, "tint": Color("8fdc6a"), "platform_mat": Mat.WOOD,
			}
