extends Node
## Entry point: switches between the title screen, a run and the death screen.

var current: Node = null


func _ready() -> void:
	randomize()
	get_tree().set_auto_accept_quit(false)
	var args := OS.get_cmdline_user_args()
	if args.has("--autotest"):
		var t: Node = load("res://tests/autoplay.gd").new()
		add_child(t)
		return
	show_menu()
	var si := args.find("--settingsshot")
	if si >= 0 and si + 1 < args.size():
		var sm := SettingsMenu.new()
		current.add_child(sm)
		await get_tree().create_timer(1.0).timeout
		for k in 4:
			sm._show_page(k)
			await get_tree().create_timer(0.3).timeout
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(args[si + 1].replace(".png", "_%d.png" % k))
		get_tree().quit()
		return
	var mi := args.find("--menushot")
	if mi >= 0 and mi + 1 < args.size():
		await get_tree().create_timer(3.0).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(args[mi + 1])
		get_tree().quit()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if current is Game:
			(current as Game).save_world()
		get_tree().quit()


func _set_screen(n: Node) -> void:
	get_tree().paused = false
	if current and is_instance_valid(current):
		current.queue_free()
	current = n
	add_child(n)


func show_menu() -> void:
	var m := MainMenu.new()
	m.new_game.connect(func(): start_game(false))
	m.continue_game.connect(func(): start_game(true))
	_set_screen(m)


func start_game(cont: bool) -> void:
	if not (cont and GameState.load_run()):
		GameState.new_run()
	var g := Game.new()
	g.died.connect(_on_died)
	g.quit_to_menu.connect(show_menu)
	_set_screen(g)
	g.start()


func _on_died(info: Dictionary) -> void:
	var d := DeathScreen.new()
	_set_screen(d)
	d.setup(info)
	d.retry.connect(func(): start_game(false))
	d.to_menu.connect(show_menu)
