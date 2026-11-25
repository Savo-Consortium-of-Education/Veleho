class_name EnemySlime
extends Enemy
## Lima: hops toward the player. Tinted per dimension.


func _init_kind() -> void:
	kind = "slime"
	display_name = "Lima"
	hw = 5
	hh = 4
	max_hp = 22.0
	contact_damage = 8.0
	sight = 150.0
	gold = 3
	bleeds = Mat.SLUDGE
	make_sprite("slime", 16, 12, [["idle", 0, 4, 6, true], ["hop", 1, 4, 10, false], ["death", 2, 4, 10, false]], -2.0)
	think = randf_range(0.3, 1.2)


func ai(delta: float, p: Player, _dist: float) -> void:
	if on_ground:
		vel.x = move_toward(vel.x, 0.0, 500.0 * delta)
		if sprite.animation == "hop" and not sprite.is_playing():
			play("idle")
		think -= delta * (0.5 if chilled > 0.0 else 1.0)
		if think <= 0.0:
			if (can_see or aggro > 0.0) and p:
				face = 1 if p.position.x > position.x else -1
				vel = Vector2(face * randf_range(60.0, 95.0), -randf_range(140.0, 185.0))
				think = randf_range(0.6, 1.1)
			else:
				face = 1 if randf() < 0.5 else -1
				vel = Vector2(face * 35.0, -100.0)
				think = randf_range(1.2, 2.6)
			sprite.play("hop")
			sprite.frame = 0
			Audio.play_at("slime_hop", position, -10.0)
