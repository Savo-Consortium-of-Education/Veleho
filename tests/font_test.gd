extends Node
## Dev tool: renders text samples to check the pixel font in Controls.

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var out := args[0] if args.size() > 0 else "user://font_test.png"
	var layer := CanvasLayer.new()
	add_child(layer)
	var root := UiUtil.root_control()
	layer.add_child(root)
	var bg := ColorRect.new()
	bg.color = Color(0.1, 0.08, 0.14)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var l1 := UiUtil.label("Label 12: Hämyluolat ÄÖÅ äöå 0123", Color.WHITE, 12, HORIZONTAL_ALIGNMENT_LEFT)
	l1.position = Vector2(10, 10)
	root.add_child(l1)
	var l2 := UiUtil.label("Label 24: Veleho", Color.WHITE, 24, HORIZONTAL_ALIGNMENT_LEFT)
	l2.position = Vector2(10, 30)
	root.add_child(l2)
	var b := UiUtil.button("Button: Uusi juoksu", func(): pass, 160)
	b.position = Vector2(10, 70)
	root.add_child(b)
	print("label font: ", l1.get_theme_font("font"), " size ", l1.get_theme_font_size("font_size"))
	print("button font: ", b.get_theme_font("font"), " size ", b.get_theme_font_size("font_size"))
	print("assets font: ", Assets.font, " root theme: ", get_tree().root.theme)
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(out)
	get_tree().quit()
