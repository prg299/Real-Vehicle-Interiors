package me.lens.rv;

import java.util.Set;
import me.zed_0xff.zombie_buddy.Exposer;
import zombie.characters.IsoGameCharacter;
import zombie.inventory.InventoryItem;
import zombie.vehicles.BaseVehicle;
import zombie.scripting.objects.VehicleScript;

/**
 * Lua-facing render state. Gameplay (entering, walking, seats, storage, lamps) lives in
 * Lua; Java clips/lights the interior, controls standing presentation, and adapts
 * native phobia calculations at their original source without changing saved traits.
 *
 * Written on the main (Lua) thread, read on the render thread, hence the volatiles and
 * the immutable {@link Light} that is replaced as a whole.
 */
@Exposer.LuaClass(name = "MELensRV")
public final class RV {
    public static final String VERSION = "2.0.13";

    static volatile BaseVehicle cutVehicle;
    /** Plane in the vehicle body's raw mesh space; fragments with a*x+b*y+c*z+d > 0 are discarded. */
    static volatile float planeA, planeB, planeC, planeD;

    /** Native skin can be cut below the lining, with a floor limit in plane-offset units. */
    record NativeCutInset(float farOffsetD, float nearOffsetD, float doorOffsetD, float floorLimitD) {
        static final NativeCutInset NONE = new NativeCutInset(0f, 0f, 0f, 0f);

        float apply(float d, boolean near, boolean door) {
            float offsetD = door ? doorOffsetD : near ? nearOffsetD : farOffsetD;
            // Zero is an exact unchanged control, including cuts already below the limit.
            return offsetD > 0f ? Math.min(d + offsetD, floorLimitD) : d;
        }
    }
    static volatile NativeCutInset nativeCutInset = NativeCutInset.NONE;

    /** Cargo body faces exposed by a cut use a lining finish on their inward side. */
    record BodyLining(float red, float green, float blue, int debug) {
        static final BodyLining NONE = new BodyLining(0f, 0f, 0f, 0);
    }
    static volatile BodyLining bodyLining = BodyLining.NONE;

    /**
     * Walls facing the camera are cut lower, like the game's cutaway of building walls:
     * the direction towards the camera in the body's mesh space (horizontal x, y) and
     * the plane offset d used on that side instead of planeD. Disabled when dNear == planeD.
     */
    static volatile float nearDirX, nearDirY, nearPlaneD;
    static volatile boolean nearCutEnabled;

    /**
     * The plane offset for ME: LENS' wheel-well boxes on the camera's side: cut almost to the
     * floor, so their tops do not show over the lowered wall like metal blocks stuck on the hull.
     */
    static volatile float wellPlaneD;

    /**
     * The plane offset of the floor itself (a hair below it) for the same boxes: on the camera's side
     * nothing of them is drawn below it. Their dark liner reaches under the floor and would show
     * through the wheel arch beside the tyre like a mud flap that KI5's camper does not have.
     */
    static volatile float wellFloorD;
    static volatile boolean wellFloorSet;

    /**
     * The room under the cut: its floor outline in the body's mesh space (x, y pairs), the
     * floor's height along the cut plane's normal, and the heights above the floor between
     * which KI5's own body details are not drawn: they stand inside ME: LENS' lining (the tips
     * of a trailer tongue's arms at the front corners, hinge blocks) and show in front of its
     * walls as black objects.
     */
    static volatile float[] roomRing = new float[0];
    static volatile float[] roomUpload = new float[160];
    static volatile float roomFloorDot, roomMin, roomMax;
    static volatile boolean roomEnabled;
    /**
     * Only faces looking up at least this much (their normal's part along the body's up, -1..1)
     * are removed: the hull's own skin tucks in under the floor looking down, and stays.
     */
    static volatile float roomNormal = -0.1f;
    static volatile boolean roomDebug;

    /**
     * Nothing ahead of the compartment you are in is cut (a bus's hood): fragments whose
     * body mesh y (towards the front) is beyond cutFrontY keep, when cutFrontEnabled.
     */
    static volatile float cutFrontY;
    static volatile boolean cutFrontEnabled;
    /** The keep only counts up to this height: body mesh z beyond it (higher up) is cut as usual (the cab's mirrors and roof lights). */
    static volatile float cutFrontTopZ = -1e9f;

    /** Which way each character standing in a camper faces (yours and, in multiplayer, the others'). */
    static final java.util.Map<IsoGameCharacter, Float> facing = new java.util.concurrent.ConcurrentHashMap<>();

    /**
     * Shading of ME: LENS' inside models: the horizontal direction the light comes from
     * in the body's mesh space, and how much brighter the sides facing it are.
     */
    static volatile float shadeX, shadeY, shadeStrength;

    /**
     * Interior light of the cut camper. Positions and reaches are in the body's mesh space.
     * A lamp with reach 0 is off.
     */
    record Light(Set<String> interiorModels, float share, float constant, float bias,
            float[] lamp0, float[] lamp1, float red, float green, float blue) {
        static final Light NONE = new Light(Set.of(), 0f, 0f, 0f, new float[4], new float[4], 0f, 0f, 0f);
    }

    static volatile Light light = Light.NONE;

    /**
     * A highlighted rectangle on the camper floor, like the game's green door marker:
     * centre and half sizes in the body's mesh space (x, y horizontal), the height
     * tolerance above and below the floor, colour, and strength (0 = hidden).
     */
    record Marker(float x, float y, float z, float halfX, float halfY, float tolerance,
            float red, float green, float blue, float strength) {
        static final Marker NONE = new Marker(0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f);
    }

    static volatile Marker marker = Marker.NONE;

    /**
     * Floor highlights while you choose where to place furniture: one per place the piece
     * fits (the one under the mouse brighter), at most {@link #MAX_SPOTS}. Replaced as a
     * whole, as the render thread reads it.
     */
    static final int MAX_SPOTS = 32;      // the box truck offers at most 21 places at once (a top box needs one below)
    static volatile Marker[] spotMarkers = new Marker[0];

    /** Tint of the ghost models (MELensRV_*_ghost), the preview of a piece before you place it. */
    static volatile float ghostRed = 0.45f, ghostGreen = 0.95f, ghostBlue = 0.55f;

    /**
     * Parts of other mods' models that ME: LENS' inside replaces in the camper you are in
     * (KI5's furnished interior and its seat cushions): model script name -> plane in the
     * body's mesh space; fragments with a*x+b*y+c*z+d > 0 are not drawn. Every other
     * camper is drawn as KI5 made it.
     */
    static final java.util.Map<String, float[]> keepPlanes = new java.util.concurrent.ConcurrentHashMap<>();

    private RV() {}

    /** Shared profile metadata; actual vehicle and seat are checked at each native update. */
    public static void registerPhobiaEnclosure(String scriptName, String passengerId, double area) {
        Phobia.registerEnclosure(scriptName, passengerId, area);
    }

    /** Read-only native diagnostic for isolated runtime verification. */
    public static String phobiaInfo(IsoGameCharacter character) {
        return Phobia.debugState(character);
    }

    public static void registerVisionHull(String scriptName, String outline, String openings) {
        Vision.register(scriptName, outline, openings);
    }

    public static String visionInfo(zombie.characters.IsoZombie observer, IsoGameCharacter target) {
        return Vision.info(observer, target);
    }

    /**
     * Resolve a runtime-added seat container without repeating VehicleScript.Loaded(),
     * which would scale the entire vehicle again. Lua owns the definitions; these
     * container fields have no Lua setters. Existing passengers/parts are untouched.
     */
    public static void bindSeatContainer(VehicleScript script, String partId, String passengerId) {
        if (script == null) throw new IllegalArgumentException("Missing vehicle script");
        var part = script.getPartById(partId);
        int seat = script.getPassengerIndex(passengerId);
        if (part == null || part.container == null || seat < 0
                || !passengerId.equals(part.container.seatId)) {
            throw new IllegalArgumentException("Invalid seat container " + partId + " for " + passengerId);
        }
        part.container.seat = seat;
    }

    public static void setKeepPlane(String modelName, double a, double b, double c, double d) {
        if (modelName != null) {
            keepPlanes.put(modelName, new float[] {(float) a, (float) b, (float) c, (float) d});
        }
    }

    /** Native binding truth, including the current live part after streamed adoption. */
    public static boolean isPartModelVisible(zombie.vehicles.VehiclePart part, String modelId) {
        BaseVehicle vehicle = part == null ? null : part.getVehicle();
        if (vehicle == null || modelId == null || vehicle.getPartById(part.getId()) != part) return false;
        for (var model : vehicle.models) {
            if (model.part == part && model.scriptModel != null && modelId.equals(model.scriptModel.id)) return true;
        }
        return false;
    }

    /** Remove only superseded bindings for this mod's same named part. No part/item changes. */
    public static boolean clearStalePartModels(zombie.vehicles.VehiclePart part) {
        BaseVehicle vehicle = part == null ? null : part.getVehicle();
        if (vehicle == null || vehicle.getPartById(part.getId()) != part) return false;
        String id = part.getId();
        if (!"MELensShell".equals(id) && !id.startsWith("MELensSpot")) return false;
        boolean removed = false;
        for (int i = vehicle.models.size() - 1; i >= 0; i--) {
            var model = vehicle.models.get(i);
            if (model.part != null && model.part != part && id.equals(model.part.getId()) && model.scriptModel != null) {
                vehicle.setModelVisible(model.part, model.scriptModel, false);
                removed = true;
            }
        }
        return removed;
    }

    /** Same as {@link #setKeepPlane}; keep planes only ever apply in the camper you are in. */
    public static void setCutKeepPlane(String modelName, double a, double b, double c, double d) {
        setKeepPlane(modelName, a, b, c, d);
    }

    public static void clearKeepPlanes() {
        keepPlanes.clear();
    }

    public static void setMarker(double x, double y, double z, double halfX, double halfY, double tolerance,
            double red, double green, double blue, double strength) {
        marker = new Marker((float) x, (float) y, (float) z, (float) halfX, (float) halfY, (float) tolerance,
                (float) red, (float) green, (float) blue, (float) strength);
    }

    public static void clearMarker() {
        marker = Marker.NONE;
    }

    /** Floor highlight {@code index} (0-based), like {@link #setMarker}. */
    public static void setSpotMarker(int index, double x, double y, double z, double halfX, double halfY, double tolerance,
            double red, double green, double blue, double strength) {
        if (index < 0 || index >= MAX_SPOTS) {
            return;
        }
        Marker[] next = java.util.Arrays.copyOf(spotMarkers, Math.max(spotMarkers.length, index + 1));
        for (int i = 0; i < next.length; i++) {
            if (next[i] == null) {
                next[i] = Marker.NONE;
            }
        }
        next[index] = new Marker((float) x, (float) y, (float) z, (float) halfX, (float) halfY, (float) tolerance,
                (float) red, (float) green, (float) blue, (float) strength);
        spotMarkers = next;
    }

    public static void clearSpotMarkers() {
        spotMarkers = new Marker[0];
    }

    public static void setGhostTint(double red, double green, double blue) {
        ghostRed = (float) red;
        ghostGreen = (float) green;
        ghostBlue = (float) blue;
    }

    /**
     * Daylight inside the cut camper: {@code share} of the scene's ambient light plus a
     * constant, biased towards surfaces facing up by {@code bias} (0..1).
     * {@code interiorModels} is a comma-separated list of model script names that are
     * entirely inside the camper (lit on every face).
     */
    public static void setInterior(String interiorModels, double share, double constant, double bias) {
        Set<String> names = interiorModels == null || interiorModels.isBlank()
                ? Set.of()
                : Set.of(interiorModels.trim().split("\\s*,\\s*"));
        Light old = light;
        light = new Light(names, (float) share, (float) constant, (float) bias,
                old.lamp0(), old.lamp1(), old.red(), old.green(), old.blue());
    }

    /** Two lamps (body mesh space, reach 0 = off) and their shared colour. */
    public static void setLamps(double x0, double y0, double z0, double reach0,
            double x1, double y1, double z1, double reach1, double red, double green, double blue) {
        Light old = light;
        light = new Light(old.interiorModels(), old.share(), old.constant(), old.bias(),
                new float[] {(float) x0, (float) y0, (float) z0, (float) reach0},
                new float[] {(float) x1, (float) y1, (float) z1, (float) reach1},
                (float) red, (float) green, (float) blue);
    }

    // ------------------------------------------------------------------------------------------------
    // Loose items: what you place or drop inside a vehicle, drawn as the game's own item models (Loose.java)
    // ------------------------------------------------------------------------------------------------

    /** The camper's passenger space to its body's mesh space (the profile's mesh scale and lift). */
    public static void setLooseBasis(double scale, double lift) {
        Loose.scale = (float) scale;
        Loose.lift = (float) lift;
    }

    /** Calibration: the scale the game's iso camera gives an item, and the most items drawn at once. */
    public static void setLooseTuning(double tileScale, double limit) {
        Loose.tileScale = (float) tileScale;
        Loose.limit = Math.max(1, (int) limit);
        Loose.clearCache();
    }

    /** Whether the game draws this item as a 3D model when it lies on the ground. */
    public static boolean hasItemModel(InventoryItem item) {
        return Loose.supported(item);
    }

    /** Whether the item can be shown inside at all: as its model, or as a flat picture of its icon. */
    public static boolean canShow(InventoryItem item) {
        return Loose.showable(item);
    }

    /** "left,up,front" size in tiles at yaw 0, or nil while the model loads (this also starts loading it). */
    public static String itemSize(InventoryItem item) {
        return Loose.size(item, null);
    }

    /** The same for an item that looks as a texture says (a bag in its own colour). */
    public static String itemSizeLook(InventoryItem item, String textureName) {
        return Loose.size(item, textureName);
    }

    /** Starts a new list of loose items for this vehicle; nothing of it is drawn in another vehicle. */
    public static void beginLoose(BaseVehicle vehicle) {
        Loose.begin(vehicle);
    }

    /** Adds an item at a passenger-space point (x left, y up, z front; tiles), turned yaw degrees; false while its model loads. */
    public static boolean addLoose(InventoryItem item, double x, double y, double z, double yawDegrees) {
        return Loose.add(item, x, y, z, yawDegrees, null, -1.0, -1.0, -1.0, false, true);
    }

    /** The same for an item that looks as a texture and a tint say (a bag in its own colour). */
    public static boolean addLooseLook(InventoryItem item, double x, double y, double z, double yawDegrees,
            String textureName, double red, double green, double blue) {
        return Loose.add(item, x, y, z, yawDegrees, textureName, red, green, blue, false, true);
    }

    public static void endLoose() {
        Loose.end();
    }

    public static void clearLoose() {
        Loose.clear();
    }

    /** The see-through preview while you choose where to put an item; red when it does not fit. */
    public static boolean setLooseGhost(InventoryItem item, double x, double y, double z, double yawDegrees, boolean fits) {
        return Loose.add(item, x, y, z, yawDegrees, null, -1.0, -1.0, -1.0, true, fits);
    }

    public static void clearLooseGhost() {
        Loose.clearGhost();
    }

    public static String looseStatus() {
        return Loose.status();
    }

    public static void retryLoose() {
        Loose.retry();
    }

    /** Forgets everything resolved and published (a new game, the main menu). */
    public static void resetLoose() {
        Loose.reset();
    }
    public static String version() {
        return VERSION;
    }

    public static void setCutaway(BaseVehicle vehicle, double a, double b, double c, double d) {
        nativeCutInset = NativeCutInset.NONE;
        bodyLining = BodyLining.NONE;
        planeA = (float) a;
        planeB = (float) b;
        planeC = (float) c;
        planeD = (float) d;
        cutVehicle = vehicle;
    }

    /**
     * Lower only native body/part cuts by this raw-mesh distance. The caller supplies
     * the plane offset at its minimum allowed height; authored lining and wheels keep
     * their own cuts. A new cutaway or zero/invalid input restores the unchanged control.
     */
    public static void setNativeCutInset(double meshUnits, double floorLimitD) {
        setNativeCutInsets(meshUnits, meshUnits, meshUnits, floorLimitD);
    }

    /** Independent native body far/near cuts and door-leaf cuts; published atomically. */
    public static void setNativeCutInsets(double farMeshUnits, double nearMeshUnits, double doorMeshUnits, double floorLimitD) {
        double normal = Math.sqrt((double) planeA * planeA + (double) planeB * planeB + (double) planeC * planeC);
        double far = farMeshUnits * normal, near = nearMeshUnits * normal, door = doorMeshUnits * normal;
        if (!Double.isFinite(far) || far < 0 || far > Float.MAX_VALUE
                || !Double.isFinite(near) || near < 0 || near > Float.MAX_VALUE
                || !Double.isFinite(door) || door < 0 || door > Float.MAX_VALUE
                || (far == 0 && near == 0 && door == 0)
                || !Double.isFinite(floorLimitD) || Math.abs(floorLimitD) > Float.MAX_VALUE) {
            nativeCutInset = NativeCutInset.NONE;
            return;
        }
        nativeCutInset = new NativeCutInset((float) far, (float) near, (float) door, (float) floorLimitD);
    }

    public static void clearCutaway() {
        Weather.clear();
        cutVehicle = null;
        nativeCutInset = NativeCutInset.NONE;
        bodyLining = BodyLining.NONE;
        wallPainted = false;
        light = Light.NONE;
        marker = Marker.NONE;
        nearCutEnabled = false;
        cutFrontEnabled = false;
        roomEnabled = false;
        doorPaintEnabled = false;
        windowCount = 0;
        jambCount = 0;
    }

    public static void setBodyLining(double red, double green, double blue) {
        if (!Double.isFinite(red) || !Double.isFinite(green) || !Double.isFinite(blue)
                || red < 0 || red > 1 || green < 0 || green > 1 || blue < 0 || blue > 1) {
            bodyLining = BodyLining.NONE;
            return;
        }
        bodyLining = new BodyLining((float) red, (float) green, (float) blue, 0);
    }

    public static void clearBodyLining() { bodyLining = BodyLining.NONE; }

    public static boolean bodyLiningActive() { return bodyLining != BodyLining.NONE; }

    /** Diagnostic render fixture: inward/up/backface classes in RGB. */
    public static void setBodyLiningDebug(boolean on) {
        setBodyLiningDebugMode(on ? 1 : 0);
    }

    /** 0 finish; 1 normal classes; 2 native texel; 3 native part mask; 4 paint alpha. */
    public static void setBodyLiningDebugMode(double mode) {
        BodyLining current = bodyLining;
        if (current != BodyLining.NONE) {
            int value = Double.isFinite(mode) && mode >= 0 && mode <= 4 && mode == Math.rint(mode) ? (int) mode : 0;
            bodyLining = new BodyLining(current.red, current.green, current.blue, value);
        }
    }

    public static void setWeatherRoom(String polygon, double floor, double ceiling) {
        Weather.setRoom(polygon, floor, ceiling);
    }

    public static String weatherInfo() { return Weather.info(); }

    /**
     * Where KI5's windows are ("x0,y0,z0,x1,y1,z1;..." boxes in the body's mesh space, at most
     * {@link #MAX_WINDOWS}). The glass is not drawn inside, and what the hull keeps of a window
     * (the seal round its opening, a pillar between two panes) would stand on the cut walls' ramps
     * as thin posts: the camper's body is not drawn inside these boxes (the shell's walls close
     * the windows from inside).
     */
    static final int MAX_WINDOWS = 12;
    static volatile float[] windowUpload = new float[MAX_WINDOWS * 6];
    static volatile int windowCount;
    static volatile float windowDark = 2.0f;        // luminance below which skin goes: 2 = all of it

    public static void setWindowBoxes(String boxes) {
        String[] entries = boxes == null || boxes.isEmpty() ? new String[0] : boxes.split(";");
        int count = Math.min(entries.length, MAX_WINDOWS);
        float[] upload = new float[MAX_WINDOWS * 6];
        try {
            for (int i = 0; i < count; i++) {
                String[] v = entries[i].split(",");
                for (int k = 0; k < 6; k++) {
                    upload[i * 6 + k] = Float.parseFloat(v[k].trim());
                }
            }
        } catch (RuntimeException bad) {
            windowCount = 0;
            return;
        }
        windowUpload = upload;
        windowCount = count;
    }

    public static void clearWindowBoxes() {
        windowCount = 0;
    }

    /**
     * Where the doors' frames are ("x0,y0,z0,x1,y1,z1;..." boxes in the body's mesh space, at most
     * {@link #MAX_JAMBS}): the dark skin of the hull inside them that looks along the camper (the jambs, black
     * rubber) is painted like the room, where it would stand black between the lining and the door leaf.
     */
    static final int MAX_JAMBS = 4;
    static volatile float[] jambUpload = new float[MAX_JAMBS * 6];
    static volatile int jambCount;

    public static void setJambBoxes(String boxes) {
        String[] entries = boxes == null || boxes.isEmpty() ? new String[0] : boxes.split(";");
        int count = Math.min(entries.length, MAX_JAMBS);
        float[] upload = new float[MAX_JAMBS * 6];
        try {
            for (int i = 0; i < count; i++) {
                String[] v = entries[i].split(",");
                for (int k = 0; k < 6; k++) {
                    upload[i * 6 + k] = Float.parseFloat(v[k].trim());
                }
            }
        } catch (RuntimeException bad) {
            jambCount = 0;
            return;
        }
        jambUpload = upload;
        jambCount = count;
    }

    public static void clearJambBoxes() {
        jambCount = 0;
    }

    /** The paint on the shell's walls (a colour 0..1), when the vehicle's owner has painted them. */
    static volatile float wallRed, wallGreen, wallBlue;
    static volatile boolean wallPainted;

    public static void setWallTint(double red, double green, double blue) {
        wallRed = (float) red;
        wallGreen = (float) green;
        wallBlue = (float) blue;
        wallPainted = true;
    }

    public static void clearWallTint() {
        wallPainted = false;
    }

    /** Developer: how dark (luminance of KI5's skin texture, 0..1) a fragment inside a window box must be to go. */
    public static void setWindowDark(double luminance) {
        windowDark = (float) luminance;
    }

    /**
     * The room's floor outline ("x,y;x,y;..." in the body's mesh space, at most {@link #MAX_RING}
     * corners), the floor's height along the cut plane's normal, and the heights above the floor
     * between which body details inside the outline are not drawn.
     */
    public static void setRoom(String points, double floorDot, double minAbove, double maxAbove) {
        String[] pairs = points == null ? new String[0] : points.split(";");
        int count = Math.min(pairs.length, MAX_RING);
        float[] ring = new float[count * 2];
        try {
            for (int i = 0; i < count; i++) {
                String[] xy = pairs[i].split(",");
                ring[i * 2] = Float.parseFloat(xy[0].trim());
                ring[i * 2 + 1] = Float.parseFloat(xy[1].trim());
            }
        } catch (RuntimeException bad) {
            roomEnabled = false;
            return;
        }
        float[] upload = new float[MAX_RING * 2];       // the whole array, as the shader takes it
        System.arraycopy(ring, 0, upload, 0, ring.length);
        roomUpload = upload;
        roomRing = ring;
        roomFloorDot = (float) floorDot;
        roomMin = (float) minAbove;
        roomMax = (float) maxAbove;
        roomEnabled = count >= 3;
    }

    public static void clearRoom() {
        roomEnabled = false;
    }

    /** Developer: the limit of {@link #roomNormal}, and painting what the clip removes magenta instead of removing it. */
    public static void setRoomNormal(double limit) {
        roomNormal = (float) limit;
    }

    public static void setRoomDebug(boolean paint) {
        roomDebug = paint;
    }

    static final int MAX_RING = 80;

    /**
     * The inside of a door leaf is bare black (KI5 only meant it to be seen from outside): in a
     * camper or a bus it is painted in this colour where it faces into the room.
     */
    static volatile float doorRed, doorGreen, doorBlue;
    static volatile boolean doorPaintEnabled;

    /**
     * Zombies beside the camper you are in are sorted against it by which side of it they stand on. The game gives a
     * character one depth by its square, so a zombie banging on the far wall was drawn in front of the whole camper
     * when its square lay in front of the camper's: its head, arms and legs showed over the cut wall and the furniture,
     * inside the camper. A zombie with the camper between it and the camera is now drawn behind the camper (the far
     * wall hides it, only what rises above the cut shows); one on the near side is drawn in front.
     */
    static volatile boolean zombieDepthEnabled = true;

    public static void setZombieDepth(boolean on) {
        zombieDepthEnabled = on;
    }

    public static void setDoorPaint(double red, double green, double blue) {
        doorRed = (float) red;
        doorGreen = (float) green;
        doorBlue = (float) blue;
        doorPaintEnabled = true;
    }

    public static void clearDoorPaint() {
        doorPaintEnabled = false;
    }

    /** Keep everything ahead of body mesh y {@code meshY} (the front of the compartment). */
    public static void setCutFront(double meshY) {
        cutFrontY = (float) meshY;
        // Each profile supplies its own optional height after this call. A
        // previous vehicle's mesh-space cutoff must never leak into this one.
        cutFrontTopZ = -1e9f;
        cutFrontEnabled = true;
    }

    /** What stands higher than body mesh z {@code meshZ} (z grows downwards) ahead of the compartment is cut like the rest. */
    public static void setCutFrontTop(double meshZ) {
        cutFrontTopZ = (float) meshZ;
    }

    public static void clearCutFront() {
        cutFrontEnabled = false;
        cutFrontTopZ = -1e9f;
    }

    /**
     * Boxes in the body's mesh space that furniture is not drawn in: the wheel wells,
     * which are open to the outside through the wheel arches. min x, y, z, max x, y, z;
     * an empty box (min > max) is off.
     */
    static final float[][] clipBoxes = {
        {1f, 1f, 1f, 0f, 0f, 0f},
        {1f, 1f, 1f, 0f, 0f, 0f},
    };

    public static void setClipBox(int index, double minX, double minY, double minZ, double maxX, double maxY, double maxZ) {
        if (index < 0 || index >= clipBoxes.length) {
            return;
        }
        clipBoxes[index] = new float[] {
            (float) Math.min(minX, maxX), (float) Math.min(minY, maxY), (float) Math.min(minZ, maxZ),
            (float) Math.max(minX, maxX), (float) Math.max(minY, maxY), (float) Math.max(minZ, maxZ),
        };
    }

    public static void clearClipBoxes() {
        for (int i = 0; i < clipBoxes.length; i++) {
            clipBoxes[i] = new float[] {1f, 1f, 1f, 0f, 0f, 0f};
        }
    }

    /** Light direction (body mesh space, horizontal) and side contrast for the inside models. */
    public static void setShade(double dirX, double dirY, double strength) {
        shadeX = (float) dirX;
        shadeY = (float) dirY;
        shadeStrength = (float) strength;
    }

    /** Cut the walls on the camera's side at plane offset {@code nearD} (same plane normal). */
    public static void setNearCut(double dirX, double dirY, double nearD) {
        nearDirX = (float) dirX;
        nearDirY = (float) dirY;
        nearPlaneD = (float) nearD;
        nearCutEnabled = true;
    }

    /** The wheel-well boxes on the camera's side are cut at plane offset {@code wellD}. */
    public static void setWellCut(double wellD) {
        wellPlaneD = (float) wellD;
    }

    /** The wheel-well boxes on the camera's side are not drawn below plane offset {@code floorD}. */
    public static void setWellFloor(double floorD) {
        wellFloorD = (float) floorD;
        wellFloorSet = true;
    }

    public static void clearNearCut() {
        nearCutEnabled = false;
    }

    public static BaseVehicle getCutawayVehicle() {
        return cutVehicle;
    }

    public static void setFacing(IsoGameCharacter character, double radians) {
        if (character != null) {
            facing.put(character, (float) radians);
        }
    }

    /** Every character's facing (yours when you leave; the others' are set again as they move). */
    public static void clearFacing() {
        facing.clear();
    }

    public static void clearFacingOf(IsoGameCharacter character) {
        if (character != null) {
            facing.remove(character);
        }
    }

    /** Mark a character as standing in a camper: it uses the normal standing animations. */
    public static void setStanding(IsoGameCharacter character, boolean isStanding) {
        if (character == null) {
            return;
        }
        if (isStanding) {
            Standing.standing.add(character);
        } else {
            Standing.standing.remove(character);
        }
    }

    public static void clearStanding() {
        Standing.standing.clear();
    }

    /** Native clip progress keeps vehicle-relative bed motion in step with the animation. */
    public static float animationProgress(IsoGameCharacter character, String clip) {
        if (character == null || character.getAnimationPlayer() == null) return 0f;
        for (var track : character.getAnimationPlayer().getMultiTrack().getTracks()) {
            if (clip.equalsIgnoreCase(track.getName()) && track.getDuration() > 0f) {
                return Math.min(1f, track.getCurrentTimeValue() / track.getDuration());
            }
        }
        return 0f;
    }

    /** Diagnostics: the animation set and state a character is in. */
    public static String animInfo(IsoGameCharacter character) {
        if (character == null || character.getActionContext() == null) {
            return "none";
        }
        zombie.characters.action.ActionContext context = character.getActionContext();
        return "group=" + (context.getGroup() == null ? "null" : context.getGroup().getName())
                + " state=" + context.getCurrentStateName()
                + " animSet=" + character.GetAnimSetName()
                + " standing=" + Standing.standing.contains(character);
    }

    /** Diagnostics for the in-game debug overlay and for test runs. */
    public static String status() {
        return "draws=" + Cutaway.drawCalls.get()
                + " cut=" + Cutaway.cutDraws.get()
                + " facing=" + Cutaway.facingCalls.get()
                + " renderer=" + (viewpointActive() ? "Viewpoint" : "isometric")
                + " shader=" + (Cutaway.shaderError == null ? "ok" : Cutaway.shaderError);
    }

    /** True only while Viewpoint's first/third-person renderer is active. */
    public static boolean viewpointActive() {
        return ViewpointCompat.active();
    }

    public static boolean useInteriorCamera(IsoGameCharacter player) {
        return ViewpointCompat.useIsometric(player);
    }

    public static String shaderError() {
        return Cutaway.shaderError;
    }

    /** Diagnostics: record every sub-model of the cut camper (see {@link #surveyInfo()}). */
    static volatile boolean survey;

    public static void setSurvey(boolean on) {
        survey = on;
        if (on) {
            Cutaway.surveyed.clear();
        }
    }

    public static String surveyInfo() {
        StringBuilder out = new StringBuilder();
        Cutaway.surveyed.forEach((name, info) -> out.append(name).append(": ").append(info).append('\n'));
        return out.toString();
    }

    /** Diagnostics: the interior light state and the uniforms the last cut draw found. */
    public static String lightInfo() {
        Light l = light;
        return "models=" + l.interiorModels()
                + " fill=" + l.share() + "/" + l.constant() + "/" + l.bias()
                + " lamp0=" + java.util.Arrays.toString(l.lamp0())
                + " lamp1=" + java.util.Arrays.toString(l.lamp1())
                + " colour=" + l.red() + "," + l.green() + "," + l.blue()
                + " lastDraw=" + Cutaway.lastLightDraw;
    }

    /** Try compiling the cutaway shaders again (after a failed compile was fixed on disk). */
    public static void retryShaders() {
        Cutaway.retryShaders();
    }
}
