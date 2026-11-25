extends Node
## Sound effects (pooled players, distance attenuation), loops and music crossfade.

const POOL := 24
const HEAR_DIST := 440.0

var listener := Vector2.ZERO
var sfx_db := 0.0
var music_db := -4.0
var _streams := {}
var _players: Array[AudioStreamPlayer] = []
var _next := 0
var _loops := {}
var _music: Array[AudioStreamPlayer] = []
var _music_idx := 0
var _music_name := ""
var _recent := {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in POOL:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_players.append(p)
	for i in 2:
		var m := AudioStreamPlayer.new()
		m.volume_db = -80.0
		m.bus = "Music"
		add_child(m)
		_music.append(m)


func _stream(path: String) -> AudioStream:
	if _streams.has(path):
		return _streams[path]
	var s: AudioStream = null
	if ResourceLoader.exists(path):
		s = load(path)
	_streams[path] = s
	return s


func sfx(name: String) -> AudioStream:
	return _stream("res://assets/sfx/%s.wav" % name)


func play(name: String, vol_db: float = 0.0, pitch: float = 1.0, pitch_var: float = 0.08) -> void:
	var s := sfx(name)
	if s == null:
		return
	# Avoid stacking the exact same sound many times in one frame.
	var now := Engine.get_process_frames()
	if _recent.get(name, -10) == now:
		return
	_recent[name] = now
	var p := _players[_next]
	_next = (_next + 1) % POOL
	p.stream = s
	p.volume_db = vol_db + sfx_db
	p.pitch_scale = maxf(0.1, pitch * (1.0 + randf_range(-pitch_var, pitch_var)))
	p.play()


func play_at(name: String, pos: Vector2, vol_db: float = 0.0, pitch: float = 1.0, pitch_var: float = 0.08) -> void:
	var d := pos.distance_to(listener)
	if d > HEAR_DIST:
		return
	play(name, vol_db - (d / HEAR_DIST) * 20.0, pitch, pitch_var)


func _make_loop(s: AudioStream) -> void:
	if s is AudioStreamWAV:
		var w := s as AudioStreamWAV
		if w.loop_mode == AudioStreamWAV.LOOP_DISABLED:
			w.loop_mode = AudioStreamWAV.LOOP_FORWARD
			w.loop_begin = 0
			w.loop_end = int(w.get_length() * w.mix_rate)


func loop_start(name: String, vol_db: float = 0.0, pitch: float = 1.0) -> void:
	var p: AudioStreamPlayer = _loops.get(name)
	if p == null:
		var s := sfx(name)
		if s == null:
			return
		_make_loop(s)
		p = AudioStreamPlayer.new()
		p.stream = s
		p.bus = "SFX"
		add_child(p)
		_loops[name] = p
	p.volume_db = vol_db + sfx_db
	p.pitch_scale = pitch
	if not p.playing:
		p.play()


func loop_set(name: String, vol_db: float, pitch: float = 1.0) -> void:
	var p: AudioStreamPlayer = _loops.get(name)
	if p:
		p.volume_db = vol_db + sfx_db
		p.pitch_scale = pitch


func loop_stop(name: String) -> void:
	var p: AudioStreamPlayer = _loops.get(name)
	if p and p.playing:
		p.stop()


func stop_all_loops() -> void:
	for k in _loops:
		(_loops[k] as AudioStreamPlayer).stop()


func play_music(name: String, fade: float = 2.0) -> void:
	if name == _music_name:
		return
	_music_name = name
	var s := _stream("res://assets/music/%s.wav" % name)
	var old := _music[_music_idx]
	_music_idx = 1 - _music_idx
	var nw := _music[_music_idx]
	if old.playing:
		var tw := create_tween()
		tw.tween_property(old, "volume_db", -60.0, fade)
		tw.tween_callback(old.stop)
	if s == null:
		return
	_make_loop(s)
	nw.stream = s
	nw.volume_db = -50.0
	nw.play()
	var tw2 := create_tween()
	tw2.tween_property(nw, "volume_db", music_db, fade)


func stop_music(fade: float = 1.5) -> void:
	_music_name = ""
	for m in _music:
		if m.playing:
			var tw := create_tween()
			tw.tween_property(m, "volume_db", -60.0, fade)
			tw.tween_callback(m.stop)
