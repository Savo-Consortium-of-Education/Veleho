class_name Mat
extends RefCounted
## Material definitions for the pixel world.
## Every cell stores a material id (0-255). Lookup tables are PackedByteArrays so
## the simulation loop can read them quickly.

# --- Kinds -------------------------------------------------------------------
const K_EMPTY := 0
const K_STATIC := 1   # solid that never moves on its own
const K_POWDER := 2
const K_LIQUID := 3
const K_GAS := 4
const K_FIRE := 5
const K_BURNING := 6  # solid that is on fire (stays in place, spreads fire)

# --- Material ids ------------------------------------------------------------
const EMPTY := 0
const BEDROCK := 1
const ROCK := 2
const DIRT := 3
const WOOD := 4
const ICE := 5
const CRYSTAL := 6
const BASALT := 7
const COAL := 8
const FUNGUS := 9
const MOSS := 10
const METAL := 11
const BRICK := 12
const OBSIDIAN := 13
const VOIDSTONE := 14
const BURNING := 15

const SAND := 20
const GRAVEL := 21
const SNOW := 22
const GUNPOWDER := 23
const ASH := 24
const SOIL := 25
const QUARTZ := 26

const WATER := 30
const OIL := 31
const ACID := 32
const LAVA := 33
const SLUDGE := 34
const BLOOD := 35
const AETHER := 36
const ELONNESTE := 37

const STEAM := 40
const SMOKE := 41
const TOXIC := 42
const FIRE := 43

# Shader effect ids (palette row 2, green channel)
const FX_NONE := 0
const FX_LIQUID := 1
const FX_FIRE := 2
const FX_LAVA := 3
const FX_SHIMMER := 4
const FX_GAS := 5
const FX_EMBER := 6

# --- Tables --------------------------------------------------------------------
static var KIND := PackedByteArray()
static var SOLID := PackedByteArray()      # blocks actors / projectiles
static var DENSITY := PackedByteArray()
static var HARD := PackedByteArray()       # 255 = indestructible
static var FLAM := PackedByteArray()       # ignition chance per contact (0-100)
static var DISSOLVE := PackedByteArray()   # acid can eat it
static var DEBRIS := PackedByteArray()     # what a destroyed cell crumbles into
static var SOFT := PackedByteArray()       # swords can cut it
static var DISPERSION := PackedByteArray() # liquid sideways reach
static var VISCOUS := PackedByteArray()    # 0-100 chance to skip a liquid update
static var CONTACT_DMG := PackedFloat32Array()  # damage / second to actors
static var CONTACT_HEAL := PackedFloat32Array() # healing / second to actors
static var IGNITES := PackedByteArray()    # sets actors on fire
static var NAMES: Array[String] = []
static var C0: Array[Color] = []
static var C1: Array[Color] = []
static var EMIT := PackedFloat32Array()
static var FXID := PackedByteArray()
static var EDGE := PackedFloat32Array()
static var palette_texture: ImageTexture


static func _static_init() -> void:
	KIND.resize(256)
	SOLID.resize(256)
	DENSITY.resize(256)
	HARD.resize(256)
	FLAM.resize(256)
	DISSOLVE.resize(256)
	DEBRIS.resize(256)
	SOFT.resize(256)
	DISPERSION.resize(256)
	VISCOUS.resize(256)
	CONTACT_DMG.resize(256)
	CONTACT_HEAL.resize(256)
	IGNITES.resize(256)
	EMIT.resize(256)
	FXID.resize(256)
	EDGE.resize(256)
	NAMES.resize(256)
	C0.resize(256)
	C1.resize(256)
	for i in 256:
		NAMES[i] = "?"
		C0[i] = Color(1, 0, 1)
		C1[i] = Color(1, 0, 1)
	NAMES[EMPTY] = "Ilma"
	C0[EMPTY] = Color(0, 0, 0, 0)
	C1[EMPTY] = Color(0, 0, 0, 0)

	# Static solids: id, name, hardness, flammability, debris, soft, c0, c1, emissive, fx
	_solid(BEDROCK, "Kallioperä", 255, 0, 0, false, "1b1720", "2a2531")
	_solid(ROCK, "Kallio", 60, 0, GRAVEL, false, "433f4c", "5f5a6b")
	_solid(DIRT, "Multa", 22, 0, SOIL, true, "4f3626", "6e4c33")
	_solid(WOOD, "Puu", 28, 30, 0, true, "5e3b21", "86592f")
	_solid(ICE, "Jää", 30, 0, SNOW, true, "8fcbe6", "c9eefc", 0.08, FX_SHIMMER)
	_solid(CRYSTAL, "Kristalli", 100, 0, QUARTZ, false, "5d3fb8", "b598ff", 0.55, FX_SHIMMER)
	_solid(BASALT, "Basaltti", 80, 0, GRAVEL, false, "29232a", "3f3640")
	_solid(COAL, "Hiili", 34, 10, ASH, false, "1a1719", "322d2e")
	_solid(FUNGUS, "Sieni", 12, 40, 0, true, "4f2862", "a85bc4", 0.4, FX_SHIMMER)
	_solid(MOSS, "Sammal", 8, 55, 0, true, "2b5321", "5b8c33")
	_solid(METAL, "Metalli", 160, 0, 0, false, "56606b", "98a4b0")
	_solid(BRICK, "Tiili", 48, 0, GRAVEL, false, "553431", "7a4a42")
	_solid(OBSIDIAN, "Obsidiaani", 110, 0, GRAVEL, false, "17122a", "372a50", 0.05)
	_solid(VOIDSTONE, "Tyhjyyskivi", 70, 0, GRAVEL, false, "251b3f", "463670", 0.12)
	_def(BURNING, "Palava aine", K_BURNING, 1, 0)
	HARD[BURNING] = 25
	DEBRIS[BURNING] = ASH
	DISSOLVE[BURNING] = 1
	SOFT[BURNING] = 1
	IGNITES[BURNING] = 1
	_col(BURNING, "b8350f", "ffb33a", 1.0, FX_EMBER)

	# Powders: id, name, density, flam, c0, c1
	_powder(SAND, "Hiekka", 30, 0, "b38f4a", "dcc07c")
	_powder(GRAVEL, "Sora", 34, 0, "4f4b57", "7d7889")
	_powder(SNOW, "Lumi", 20, 0, "d3e2ee", "ffffff", 0.05)
	_powder(GUNPOWDER, "Ruuti", 28, 100, "252326", "48444a")
	_powder(ASH, "Tuhka", 18, 0, "4d4846", "77706b")
	_powder(SOIL, "Irtomulta", 29, 0, "47301f", "6a4930")
	_powder(QUARTZ, "Kvartsihiekka", 30, 0, "a493dc", "e6ddff", 0.15)

	# Liquids: id, name, density, dispersion, viscous, flam, c0, c1, alpha, emissive
	_liquid(WATER, "Vesi", 10, 5, 0, 0, "2a63a8", "3f86c9", 0.72)
	_liquid(OIL, "Öljy", 8, 3, 10, 70, "33281b", "4f3d27", 0.92)
	_liquid(ACID, "Happo", 11, 4, 0, 0, "6bd02e", "b2ff63", 0.82, 0.45)
	_liquid(LAVA, "Laava", 14, 2, 55, 0, "e8480c", "ffc23d", 1.0, 1.0)
	FXID[LAVA] = FX_LAVA
	_liquid(SLUDGE, "Myrkkyliete", 12, 2, 35, 0, "4f6b14", "86a52a", 0.9, 0.2)
	_liquid(BLOOD, "Veri", 10, 3, 10, 0, "7a0c1a", "a81a2a", 0.9)
	_liquid(AETHER, "Eetteri", 9, 5, 0, 0, "4cc8f5", "c2f4ff", 0.7, 0.75)
	_liquid(ELONNESTE, "Elonneste", 10, 4, 0, 0, "e0487e", "ffb3d1", 0.85, 0.5)

	# Gases: id, name, density, c0, c1, alpha, emissive
	_gas(STEAM, "Höyry", 2, "b9c5d1", "e8eef4", 0.4)
	_gas(SMOKE, "Savu", 3, "2f2b2e", "514c50", 0.55)
	_gas(TOXIC, "Myrkkykaasu", 3, "7da82f", "b6e055", 0.4, 0.15)
	_def(FIRE, "Tuli", K_FIRE, 0, 1)
	IGNITES[FIRE] = 1
	_col(FIRE, "ff6a14", "fff0a0", 1.0, FX_FIRE)

	# Contact damage (per second) and ignition
	CONTACT_DMG[ACID] = 32.0
	CONTACT_DMG[LAVA] = 70.0
	CONTACT_DMG[SLUDGE] = 7.0
	CONTACT_DMG[TOXIC] = 5.0
	IGNITES[LAVA] = 1
	CONTACT_HEAL[ELONNESTE] = 9.0


static func _def(id: int, n: String, kind: int, dens: int, flam: int) -> void:
	NAMES[id] = n
	KIND[id] = kind
	DENSITY[id] = dens
	FLAM[id] = flam
	SOLID[id] = 1 if kind == K_STATIC or kind == K_POWDER or kind == K_BURNING else 0


static func _col(id: int, a: String, b: String, emissive: float = 0.0, fx: int = FX_NONE, alpha: float = 1.0) -> void:
	var ca := Color(a)
	var cb := Color(b)
	ca.a = alpha
	cb.a = alpha
	C0[id] = ca
	C1[id] = cb
	EMIT[id] = emissive
	FXID[id] = fx


static func _solid(id: int, n: String, hard: int, flam: int, debris: int, soft: bool, a: String, b: String, emissive: float = 0.0, fx: int = FX_NONE) -> void:
	_def(id, n, K_STATIC, 50, flam)
	HARD[id] = hard
	DEBRIS[id] = debris
	SOFT[id] = 1 if soft else 0
	DISSOLVE[id] = 1 if hard < 55 else 0
	EDGE[id] = 1.0
	_col(id, a, b, emissive, fx)


static func _powder(id: int, n: String, dens: int, flam: int, a: String, b: String, emissive: float = 0.0) -> void:
	_def(id, n, K_POWDER, dens, flam)
	HARD[id] = 6
	SOFT[id] = 1
	DISSOLVE[id] = 1
	EDGE[id] = 0.45
	_col(id, a, b, emissive)


static func _liquid(id: int, n: String, dens: int, disp: int, visc: int, flam: int, a: String, b: String, alpha: float, emissive: float = 0.0) -> void:
	_def(id, n, K_LIQUID, dens, flam)
	HARD[id] = 4
	DISPERSION[id] = disp
	VISCOUS[id] = visc
	EDGE[id] = 0.35
	_col(id, a, b, emissive, FX_LIQUID, alpha)


static func _gas(id: int, n: String, dens: int, a: String, b: String, alpha: float, emissive: float = 0.0) -> void:
	_def(id, n, K_GAS, dens, 0)
	HARD[id] = 1
	_col(id, a, b, emissive, FX_GAS, alpha)


## 256x4 palette texture: row0 = colour A, row1 = colour B,
## row2 = (emissive, fx id / 255, edge strength, 1), row3 = (solid, 0, 0, 1).
static func palette() -> ImageTexture:
	if palette_texture == null:
		_build_palette()
	return palette_texture


static func _build_palette() -> void:
	var img := Image.create_empty(256, 4, false, Image.FORMAT_RGBA8)
	for i in 256:
		img.set_pixel(i, 0, C0[i])
		img.set_pixel(i, 1, C1[i])
		img.set_pixel(i, 2, Color(clampf(EMIT[i], 0.0, 1.0), FXID[i] / 255.0, clampf(EDGE[i], 0.0, 1.0), 1.0))
		img.set_pixel(i, 3, Color(1.0 if SOLID[i] != 0 else 0.0, 0, 0, 1))
	palette_texture = ImageTexture.create_from_image(img)


static func is_solid(m: int) -> bool:
	return SOLID[m] != 0


static func color_of(m: int, t: float) -> Color:
	return C0[m].lerp(C1[m], t)
