extends Node
## Run state, deterministic seeds, save/load and permadeath bookkeeping.

var SAVE_PATH := "user://veleho_run.save"
var META_PATH := "user://veleho_meta.save"

var WORLD_PATH := "user://veleho_world.save"
const BOSS_EVERY := 3

var run: Dictionary = {}
var meta: Dictionary = {"runs": 0, "deaths": 0, "best_level": 0, "kills": 0, "gold": 0}
var last_death: Dictionary = {}
var force_dim := ""  # tests: force a dimension for every level
var settings := GameSettings.new()


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if _dev_run():
		# Automated tests never touch the player's own saves, stats or settings.
		SAVE_PATH = "user://devtest_run.save"
		META_PATH = "user://devtest_meta.save"
		WORLD_PATH = "user://devtest_world.save"
	settings.ensure_buses()
	apply_default_input()
	if not _dev_run():
		settings.load_settings()
	if _dev_run():
		# automated tests keep their own window placement and ignore user display settings
		settings.apply_audio()
		settings.apply_bindings()
	else:
		settings.apply_all()
	_load_meta()


# ---------------------------------------------------------------------------
# Input map (defined in code so project.godot stays small)
# ---------------------------------------------------------------------------
const DEFAULT_KEYS := {
	"move_left": [KEY_A, KEY_LEFT],
	"move_right": [KEY_D, KEY_RIGHT],
	"jump": [KEY_W, KEY_SPACE, KEY_UP],
	"down": [KEY_S, KEY_DOWN],
	"interact": [KEY_E],
	"drink": [KEY_F],
	"inventory": [KEY_TAB, KEY_I],
	"pause": [KEY_ESCAPE, KEY_P],
	"slot_1": [KEY_1],
	"slot_2": [KEY_2],
	"slot_3": [KEY_3],
	"slot_4": [KEY_4],
}
const DEFAULT_MOUSE := {
	"fire": MOUSE_BUTTON_LEFT,
	"alt_fire": MOUSE_BUTTON_RIGHT,
	"next_weapon": MOUSE_BUTTON_WHEEL_DOWN,
	"prev_weapon": MOUSE_BUTTON_WHEEL_UP,
}


func apply_default_input() -> void:
	for action in DEFAULT_KEYS:
		if InputMap.has_action(action):
			InputMap.action_erase_events(action)
		_key_action(action, DEFAULT_KEYS[action])
	for action in DEFAULT_MOUSE:
		if InputMap.has_action(action):
			InputMap.action_erase_events(action)
		_mouse_action(action, DEFAULT_MOUSE[action])


func _dev_run() -> bool:
	var args := OS.get_cmdline_user_args()
	return args.has("--autotest") or args.has("--menushot") or args.has("--settingsshot")


func is_boss_level(level: int) -> bool:
	return level % BOSS_EVERY == 0


func _key_action(action: String, keys: Array) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	for k in keys:
		var ev := InputEventKey.new()
		ev.physical_keycode = k
		InputMap.action_add_event(action, ev)


func _mouse_action(action: String, button: MouseButton) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	var ev := InputEventMouseButton.new()
	ev.button_index = button
	InputMap.action_add_event(action, ev)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
func new_run() -> void:
	var r := RandomNumberGenerator.new()
	r.randomize()
	var s := r.randi() & 0x7fffffff
	run = {
		"seed": s,
		"level": 1,
		"player": {
			"hp": 100.0, "max_hp": 100.0,
			"mana_max": 100.0, "mana_regen": 30.0,
			"lev_max": 2.6, "speed": 1.0, "dmg_mult": 1.0,
			"fire_immune": false, "blast_resist": 0.0, "lifesteal": 0.0, "reach_mult": 1.0,
			"perks": [], "slot": 0,
			"weapons": WeaponGen.starter_kit(s),
			"bag": WeaponGen.starter_bag(s),
		},
		"stats": {"kills": 0, "gold": 0, "time": 0.0},
	}
	meta["runs"] = int(meta["runs"]) + 1
	_save_meta()
	delete_world_save()


func dimension_for_level(level: int) -> String:
	if force_dim != "":
		return force_dim
	if level <= 1:
		return "caves"
	var r := RandomNumberGenerator.new()
	r.seed = hash([int(run["seed"]), "dims"])
	var prev := "caves"
	var result := "caves"
	for l in range(2, level + 1):
		var options: Array[String] = []
		for d in Dimensions.IDS:
			if d != prev:
				options.append(d)
		result = options[r.randi() % options.size()]
		prev = result
	return result


func level_seed(level: int) -> int:
	return hash([int(run["seed"]), level, "level"]) & 0x7fffffff


func has_save() -> bool:
	return FileAccess.file_exists(SAVE_PATH)


func write_world_save(data: Dictionary) -> bool:
	var f := FileAccess.open_compressed(WORLD_PATH, FileAccess.WRITE, FileAccess.COMPRESSION_ZSTD)
	if f == null:
		return false
	f.store_var(data)
	f.close()
	return true


## Returns the mid-level world save if it belongs to the current run and level.
func load_world_save() -> Dictionary:
	if not FileAccess.file_exists(WORLD_PATH):
		return {}
	var f := FileAccess.open_compressed(WORLD_PATH, FileAccess.READ, FileAccess.COMPRESSION_ZSTD)
	if f == null:
		return {}
	var data = f.get_var()
	f.close()
	if typeof(data) != TYPE_DICTIONARY:
		return {}
	if int(data.get("seed", -1)) != int(run.get("seed", -2)) or int(data.get("level", -1)) != int(run.get("level", -2)):
		return {}
	return data


func has_world_save() -> bool:
	return FileAccess.file_exists(WORLD_PATH)


func delete_world_save() -> void:
	if FileAccess.file_exists(WORLD_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(WORLD_PATH))


func save_run() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(var_to_str(run))
		f.close()


func load_run() -> bool:
	if not has_save():
		return false
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return false
	var data = str_to_var(f.get_as_text())
	f.close()
	if typeof(data) != TYPE_DICTIONARY or not data.has("seed"):
		return false
	run = data
	return true


func delete_save() -> void:
	if has_save():
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH))


func record_death(cause: String, killer: String) -> void:
	var st: Dictionary = run.get("stats", {})
	last_death = {
		"cause": cause,
		"killer": killer,
		"level": int(run.get("level", 1)),
		"dimension": Dimensions.get_def(dimension_for_level(int(run.get("level", 1))))["name"],
		"kills": int(st.get("kills", 0)),
		"gold": int(st.get("gold", 0)),
		"time": float(st.get("time", 0.0)),
		"seed": int(run.get("seed", 0)),
	}
	meta["deaths"] = int(meta["deaths"]) + 1
	meta["best_level"] = maxi(int(meta["best_level"]), last_death["level"])
	meta["kills"] = int(meta["kills"]) + last_death["kills"]
	meta["gold"] = int(meta["gold"]) + last_death["gold"]
	_save_meta()
	delete_save()
	delete_world_save()


func _load_meta() -> void:
	if not FileAccess.file_exists(META_PATH):
		return
	var f := FileAccess.open(META_PATH, FileAccess.READ)
	if f == null:
		return
	var data = str_to_var(f.get_as_text())
	f.close()
	if typeof(data) == TYPE_DICTIONARY:
		for k in data:
			meta[k] = data[k]


func _save_meta() -> void:
	var f := FileAccess.open(META_PATH, FileAccess.WRITE)
	if f:
		f.store_string(var_to_str(meta))
		f.close()
