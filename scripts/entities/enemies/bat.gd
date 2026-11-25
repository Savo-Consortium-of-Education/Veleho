class_name EnemyBat
extends Enemy
## Siipiö: erratic flyer that dives at the player and retreats after biting.

var flee := 0.0
var wander_dir := Vector2.RIGHT


func _init_kind() -> void:
	kind = "bat"
	display_name = "Siipiö"
	hw = 4
	hh = 3
	max_hp = 10.0
	contact_damage = 6.0
	sight = 190.0
	gold = 2
	flying = true
	gravity_scale = 0.0
	make_sprite("bat", 16, 12, [["fly", 0, 4, 12, true], ["death", 1, 3, 10, false]], 0.0)
	wander_dir = Vector2.from_angle(randf() * TAU)


func ai(delta: float, p: Player, _dist: float) -> void:
	think -= delta
	flee = maxf(0.0, flee - delta)
	var desired := Vector2.ZERO
	if p and (can_see or aggro > 0.0):
		var to := p.center() + Vector2(0, -6) - center()
		var perp := to.normalized().orthogonal()
		desired = to.normalized() * 80.0 + perp * sin(anim_time * 5.0) * 45.0
		if flee > 0.0:
			desired = -to.normalized() * 90.0 + Vector2(0, -30)
		face = 1 if to.x > 0 else -1
		if think <= 0.0:
			think = randf_range(1.5, 3.0)
			Audio.play_at("bat_screech", position, -14.0)
	else:
		if think <= 0.0:
			think = randf_range(1.0, 2.2)
			wander_dir = Vector2.from_angle(randf() * TAU)
		desired = wander_dir * 30.0
		face = 1 if desired.x > 0 else -1
	if chilled > 0.0:
		desired *= 0.5
	var before := vel
	vel = vel.lerp(desired, 3.0 * delta)
	if absf(before.x) > 5.0 and blocked_ahead(1 if before.x > 0 else -1):
		wander_dir.x = -wander_dir.x
	sprite.position.y = sin(anim_time * 8.0)


func on_touch_player(_p: Player) -> void:
	flee = 0.7
