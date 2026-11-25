class_name MainMenu
extends Node2D
## Title screen with a live falling-sand cave in the background.

signal new_game
signal continue_game

var world: PixelWorld
var t := 0.0
var emitters: Array = []


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	get_tree().paused = false
	world = PixelWorld.new()
	add_child(world)
	var d := Dimensions.get_def(["caves", "forge", "crystal", "fungal", "frost"][randi() % 5]).duplicate(true)
	d["size"] = Vector2i(480, 270)
	d["pools"] = 4
	d["structures"] = {"platforms": 2, "ruins": 0, "kegs": 0}
	d["enemy_base"] = 0
	var gen := WorldGen.new()
	gen.generate(world, randi(), 1, d)
	world.set_background(d["bg_dark"], d["bg_light"], d["stars"])
	var liquids: Array = d["liquids"].keys()
	for k in 3:
		emitters.append([randi_range(40, 440), [Mat.SAND, liquids[randi() % liquids.size()], Mat.GRAVEL][k], randf_range(0.0, 3.0)])
	var cam := Camera2D.new()
	cam.position = Vector2(240, 135)
	add_child(cam)
	cam.make_current()
	_build_ui()
	Audio.play_music("menu")


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	var root := UiUtil.root_control()
	layer.add_child(root)
	var shade := ColorRect.new()
	shade.color = Color(0.02, 0.01, 0.05, 0.55)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(shade)
	var logo := TextureRect.new()
	logo.texture = Assets.tex("logo")
	logo.position = Vector2(240 - logo.texture.get_width() / 2, 22)
	logo.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(logo)
	var sub := UiUtil.label("Pikselimaailman velho · prototyyppi", Color("c8b8e8"))
	sub.position = Vector2(0, 76)
	sub.size = Vector2(480, 12)
	root.add_child(sub)
	var box := VBoxContainer.new()
	box.position = Vector2(240 - 85, 100)
	box.custom_minimum_size = Vector2(170, 0)
	box.add_theme_constant_override("separation", 5)
	root.add_child(box)
	var first: Button = null
	if GameState.has_save() and GameState.load_run():
		var lvl := int(GameState.run.get("level", 1))
		var dn: String = Dimensions.get_def(GameState.dimension_for_level(lvl))["name"]
		var mid := " (kesken)" if GameState.has_world_save() else ""
		first = UiUtil.button("Jatka – taso %d, %s%s" % [lvl, dn, mid], func(): continue_game.emit(), 170)
		box.add_child(first)
	var ng := UiUtil.button("Uusi juoksu (hylkää tallennuksen)" if first != null else "Uusi juoksu", func(): _confirm_new(), 170)
	box.add_child(ng)
	if first == null:
		first = ng
	box.add_child(UiUtil.button("Asetukset", func(): add_child(SettingsMenu.new()), 170))
	# In the browser quitting would only freeze the page; players just close the tab.
	if not OS.has_feature("web"):
		box.add_child(UiUtil.button("Lopeta", func(): get_tree().quit(), 170))
	first.grab_focus()
	var m := GameState.meta
	var stats := UiUtil.label("Juoksuja %d · Kuolemia %d · Paras taso %d" % [int(m["runs"]), int(m["deaths"]), int(m["best_level"])], Color("8f86a8"))
	stats.position = Vector2(0, 206)
	stats.size = Vector2(480, 12)
	root.add_child(stats)
	var help := UiUtil.label("A/D liiku · W/välilyönti hyppää, pidä leijuaksesi · hiiri tähtää ja käyttää asetta\n1–4 / rulla vaihtaa asetta · E poimii · Esc tauko · F3 tiedot", Color("a89cc0"))
	help.position = Vector2(0, 228)
	help.size = Vector2(480, 30)
	root.add_child(help)


func _confirm_new() -> void:
	# Starting a new run abandons the saved one (hardcore).
	if GameState.has_save():
		GameState.delete_save()
	GameState.delete_world_save()
	new_game.emit()


func _physics_process(delta: float) -> void:
	t += delta
	for e in emitters:
		e[2] -= delta
		if e[2] < 0.0:
			if e[2] < -2.5:
				e[2] = randf_range(2.0, 5.0)
				e[0] = randi_range(40, 440)
			else:
				for k in 2:
					world.set_cell(int(e[0]) + randi_range(-1, 1), 4, int(e[1]))
	if randf() < 0.01:
		world.explode(randi_range(60, 420), randi_range(60, 220), randi_range(5, 10), 70.0, randf() < 0.4)
	world.step()


func _process(_delta: float) -> void:
	world.upload()
