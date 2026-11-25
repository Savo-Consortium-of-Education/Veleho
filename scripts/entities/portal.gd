class_name Portal
extends Node2D
## Dimensional gate at the end of every level.

var game: Game
var sprite: AnimatedSprite2D
var active := true
var sealed := false
var t := 0.0
var _humming := false
var _sealed_msg := 0.0


func setup(g: Game, pos: Vector2) -> void:
	game = g
	position = pos
	z_index = 1
	sprite = AnimatedSprite2D.new()
	sprite.sprite_frames = Assets.frames("portal", 24, 32, [["swirl", 0, 8, 10, true]])
	sprite.play("swirl")
	add_child(sprite)


func _physics_process(delta: float) -> void:
	if game == null or game.paused_for_ui:
		return
	t += delta
	_sealed_msg -= delta
	if sealed:
		sprite.modulate = Color(0.3, 0.26, 0.4)
		sprite.speed_scale = 0.25
		game.add_light(position, 30.0, Color(0.5, 0.3, 0.6) * 0.5)
		var pl0 := game.player
		if pl0 and not pl0.dead and pl0.position.distance_to(position) < 26.0 and _sealed_msg <= 0.0:
			_sealed_msg = 4.0
			game.hud.message("Portti on sinetöity. Kukista Portinvartija!", Color("c8a8ff"))
		return
	game.add_light(position, 80.0, Color(0.55, 0.4, 1.0) * (0.85 + 0.15 * sin(t * 3.0)))
	if game.particles and randf() < 0.3:
		var a := randf() * TAU
		var r := randf_range(10.0, 16.0)
		var p := position + Vector2(cos(a) * r * 0.6, sin(a) * r)
		game.particles.spawn(p, (position - p) * 1.5, Color(0.7, 0.55, 1.0) if randf() < 0.5 else Color(0.5, 0.95, 1.0), 0.5, 0.0)
	var pl := game.player
	if not active or pl == null or pl.dead:
		return
	var d := pl.position.distance_to(position)
	if d < 220.0:
		Audio.loop_start("portal_hum", lerpf(-8.0, -32.0, d / 220.0))
		_humming = true
	elif _humming:
		Audio.loop_stop("portal_hum")
		_humming = false
	if absf(pl.position.x - position.x) < 9.0 and absf(pl.position.y - position.y) < 15.0:
		active = false
		Audio.loop_stop("portal_hum")
		game.enter_portal()


func unseal() -> void:
	sealed = false
	sprite.modulate = Color.WHITE
	sprite.speed_scale = 1.0
	Audio.play("portal_unseal")
	game.flash(position, 140.0, Color(0.7, 0.5, 1.0), 0.8)
	if game.particles:
		game.particles.burst(position, 40, Color(0.75, 0.6, 1.0), 120.0, 0.8, 0.0)


func _exit_tree() -> void:
	if _humming:
		Audio.loop_stop("portal_hum")
