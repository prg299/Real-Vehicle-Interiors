package me.lens.rv;

import java.util.concurrent.atomic.AtomicLong;
import org.joml.Matrix4f;
import org.joml.Vector4f;
import org.lwjgl.opengl.GL20;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoZombie;
import zombie.vehicles.BaseVehicle;
import zombie.core.Core;
import zombie.core.opengl.ShaderProgram;
import zombie.core.skinnedmodel.ModelManager;
import zombie.core.skinnedmodel.model.Model;
import zombie.core.skinnedmodel.model.ModelInstance;
import zombie.core.skinnedmodel.model.ModelInstanceRenderData;
import zombie.core.skinnedmodel.model.ModelMesh;
import zombie.core.skinnedmodel.model.ModelSlotRenderData;
import zombie.core.skinnedmodel.shader.Shader;
import zombie.core.skinnedmodel.shader.ShaderManager;
import zombie.scripting.objects.ModelScript;

/**
 * Render-thread half of the cutaway. For the one camper the player is inside, every
 * sub-model that reaches above the cut plane is drawn with an ME: LENS shader that is
 * identical in inputs to the original but discards fragments above the plane. The
 * original shader is restored as soon as that single draw returns, so other vehicles,
 * other copies of the same model and every KI5 part state stay untouched.
 *
 * Every other camper is drawn exactly as KI5 made it: ME: LENS' own inside (the shell and
 * the furniture, models named MELens*) is only drawn in the camper you are in.
 */
public final class Cutaway {
    static final AtomicLong drawCalls = new AtomicLong();
    static final AtomicLong cutDraws = new AtomicLong();
    static final AtomicLong facingCalls = new AtomicLong();
    private static final AtomicLong diagnostics = new AtomicLong();
    static volatile String shaderError;
    /** Diagnostics for {@link RV#lightInfo()}: the last interior draw and which uniforms it found. */
    static volatile String lastLightDraw = "none";

    private static final String VEHICLE_SHADER = "melens_cutaway_vehicle";
    private static final String PART_SHADER = "melens_cutaway_part";
    private static final Shader[] shaders = new Shader[4];
    private static final boolean[] failed = new boolean[4];
    private static volatile boolean retry;

    // DrawVehicle is not re-entrant, but keep the swap per thread anyway.
    private static final ThreadLocal<Model> swappedModel = new ThreadLocal<>();
    private static final ThreadLocal<Shader> originalShader = new ThreadLocal<>();

    private static final Matrix4f scratch = new Matrix4f();
    private static final Vector4f plane = new Vector4f();

    private Cutaway() {}

    static void retryShaders() {
        retry = true;
    }

    /** Returns true when the draw is to be skipped. */
    public static boolean beginVehicleDraw(Model model, ModelSlotRenderData slot, ModelInstanceRenderData inst) {
        if (ViewpointCompat.active()) {
            return false;
        }
        drawCalls.incrementAndGet();
        if (slot == null || inst == null || model == null) {
            return false;
        }
        Object vehicle = RV.cutVehicle;
        boolean isCut = vehicle != null && slot.object == vehicle;
        boolean own = isOwnInside(inst);
        if (!isCut) {
            return own;
        }
        // Parts of KI5's models that ME: LENS' inside replaces, removed in the camper you are in.
        float[] keep = keepPlaneFor(inst, RV.keepPlanes);
        Shader original = model.effect;
        if (original == null || String.valueOf(original.getName()).startsWith("melens_")) {
            return false;
        }
        Matrix4f body = bodyTransform(slot);
        if (body == null) {
            return own;
        }
        if (isCut && RV.survey) {
            survey(model, inst, body);
        }
        // Road wheels remain outside the room. Keep their native material and
        // texture binding even when the body and lining above them are cut.
        if (inst.modelInstance instanceof zombie.core.skinnedmodel.model.VehicleSubModelInstance sub
                && sub.modelInfo != null && sub.modelInfo.part != null
                && sub.modelInfo.part.getWheelIndex() >= 0) return false;
        // scratch maps this sub-model's mesh space into the body's mesh space. Parts from
        // other FBX files (awning, jack) have their own axes and offsets.
        scratch.set(body).invert().mul(inst.xfrm);
        RV.Light light = isCut ? RV.light : RV.Light.NONE;
        // ME: LENS furniture is never cut, like furniture in the game's own cutaway: only
        // the walls are. It still gets the interior light.
        boolean furniture = isCut && isFurniture(inst);
        float lightMode = !isCut ? 0f : furniture ? 1f : lightMode(inst, original, light);
        RV.NativeCutInset nativeInset = own ? RV.NativeCutInset.NONE : RV.nativeCutInset;
        // Use the actual part contract, including trunk doors whose mesh name does
        // not pass the narrower door-paint classifier below.
        boolean nativeDoor = !own
                && inst.modelInstance instanceof zombie.core.skinnedmodel.model.VehicleSubModelInstance nativePart
                && nativePart.modelInfo != null && nativePart.modelInfo.part != null
                && nativePart.modelInfo.part.getDoor() != null;
        float drawPlaneD = nativeInset.apply(RV.planeD, false, nativeDoor);
        float drawNearPlaneD = nativeInset.apply(RV.nearPlaneD, true, nativeDoor);
        // Skip sub-models that nothing touches: entirely below the lowest cut (the camera
        // side's, when that is on), not lit as interior, and nothing to remove.
        if (keep == null && model.isStatic && lightMode != 1f) {
            float lowestD = RV.nearCutEnabled ? Math.max(drawPlaneD, drawNearPlaneD) : drawPlaneD;
            plane.set(RV.planeA, RV.planeB, RV.planeC, lowestD);
            scratch.transformTranspose(plane);
            if (entirelyBelow(model.mesh, plane)) {
                return false;
            }
        }
        Shader cut = shader(original.isVehicleShader() ? VEHICLE_SHADER : PART_SHADER, model.isStatic, original.isVehicleShader());
        if (cut == null) {
            // Without the cutaway shader the camper stays KI5's own model, inside too.
            return own;
        }
        cut.Start();
        ShaderProgram program = cut.getShaderProgram();
        // Preserve the source material's paint mode. NoRandom liveries are baked;
        // ordinary vehicle_multiuv materials use the vehicle's native HSV mask.
        if (original.isVehicleShader()) program.setValue("MELensVehiclePaint",
            "vehicle_multiuv".equals(original.getName()) ? 1f : 0f);
        program.setValue("MELensToBody", scratch);
        if (!isCut || furniture || isCabBulkhead(inst)) {
            program.setVector4("MELensBodyPlane", 0f, 0f, 0f, -1.0f);
            program.setVector4("MELensNearCut", 0f, 0f, 0f, 0f);
            program.setVector4("MELensCutFront", 0f, 0f, 0f, 0f);
        } else {
            program.setVector4("MELensBodyPlane", RV.planeA, RV.planeB, RV.planeC, drawPlaneD);
            program.setVector4("MELensNearCut", RV.nearDirX, RV.nearDirY, drawNearPlaneD, RV.nearCutEnabled ? 1f : 0f);
            program.setVector4("MELensCutFront", RV.cutFrontY, RV.cutFrontTopZ, 0f, RV.cutFrontEnabled ? 1f : 0f);
        }
        if (keep != null) {
            program.setVector4("MELensKeepPlane", keep[0], keep[1], keep[2], keep[3]);
        } else {
            program.setVector4("MELensKeepPlane", 0f, 0f, 0f, -1.0f);
        }
        program.setVector4("MELensBodyUp", RV.planeA, RV.planeB, RV.planeC, lightMode);
        Model bodyModel = slot.modelSlot.model.model;
        ModelMesh bodyMesh = bodyModel == null ? null : bodyModel.mesh;
        if (bodyMesh != null && bodyMesh.minXyz.x <= bodyMesh.maxXyz.x) {
            program.setVector4("MELensShape", bodyMesh.minXyz.x, bodyMesh.minXyz.y, bodyMesh.maxXyz.x, bodyMesh.maxXyz.y);
        } else {
            program.setVector4("MELensShape", 0f, 0f, 0f, 0f);
        }
        program.setVector4("MELensFill", light.share(), light.constant(), light.bias(), 0f);
        float[] lamp0 = light.lamp0();
        float[] lamp1 = light.lamp1();
        program.setVector4("MELensLamp0", lamp0[0], lamp0[1], lamp0[2], lamp0[3]);
        program.setVector4("MELensLamp1", lamp1[0], lamp1[1], lamp1[2], lamp1[3]);
        program.setVector3("MELensLampColour", light.red(), light.green(), light.blue());
        RV.Marker marker = isCut ? RV.marker : RV.Marker.NONE;
        program.setVector4("MELensMarker", marker.x(), marker.y(), marker.z(), marker.strength());
        program.setVector4("MELensMarkerSize", marker.halfX(), marker.halfY(), marker.tolerance(), 0f);
        program.setVector3("MELensMarkerColour", marker.red(), marker.green(), marker.blue());
        program.setVector4("MELensShade", RV.shadeX, RV.shadeY, RV.shadeStrength, furniture ? 1f : 0f);
        // placing furniture: the places it fits, highlighted on the floor, and its ghost
        RV.Marker[] spots = isCut ? RV.spotMarkers : NO_SPOTS;
        if (!original.isVehicleShader()) {
            program.setValue("MELensSpotCount", (float) spots.length);
            int[][] locations = spotLocations(program);
            for (int i = 0; i < spots.length; i++) {
                RV.Marker s = spots[i] == null ? RV.Marker.NONE : spots[i];
                if (locations[0][i] >= 0) {
                    program.setVector4(locations[0][i], s.x(), s.y(), s.z(), s.strength());
                    program.setVector4(locations[1][i], s.halfX(), s.halfY(), s.tolerance(), 0f);
                    program.setVector3(locations[2][i], s.red(), s.green(), s.blue());
                }
            }
            boolean ghost = furniture && isGhost(inst);
            program.setVector4("MELensGhost", RV.ghostRed, RV.ghostGreen, RV.ghostBlue, ghost ? 1f : 0f);
            // the paint the walls were given
            boolean painted = isCut && RV.wallPainted && isShellWalls(inst);
            program.setVector4("MELensWallTint", RV.wallRed, RV.wallGreen, RV.wallBlue, painted ? 0.9f : 0f);
            program.setVector4("MELensUv", 0f, 0f, 1f, 1f);
            // Keep wheel-well lids intact; the shader clips only the liner below the floor.
            program.setVector4("MELensWellCut", RV.wellPlaneD, RV.wellFloorD, RV.wellFloorSet ? 1f : 0f,
                    isCut && RV.nearCutEnabled ? 1f : 0f);
        } else {
            RV.BodyLining lining = RV.bodyLining;
            boolean lineBody = isCut && RV.roomEnabled && isBody(slot, inst) && lining != RV.BodyLining.NONE;
            program.setVector4("MELensBodyLining", lining.red(), lining.green(), lining.blue(),
                    lineBody ? 1f + lining.debug() : 0f);
            // a door leaf's bare black inside is painted like the room
            boolean doorLeaf = isCut && isDoor(inst);
            boolean door = doorLeaf && RV.doorPaintEnabled;
            program.setVector4("MELensDoor", RV.doorRed, RV.doorGreen, RV.doorBlue, door ? 1f : 0f);
            // KI5's own body details standing inside ME: LENS' lining are not drawn
            // (not a door leaf: its lower 30 cm stand inside the outline at the doorway, and without them
            // the doorway shows the ground outside)
            boolean room = isCut && !furniture && RV.roomEnabled && !doorLeaf;
            float[] ring = RV.roomRing;
            program.setVector4("MELensRoom", room ? ring.length / 2 : 0f, RV.roomFloorDot, RV.roomMin, RV.roomMax);
            // (the camper's body only: its tank, tyres and hitch stand in some windows' boxes)
            int windows = isCut && !furniture && isBody(slot, inst) ? RV.windowCount : 0;
            program.setVector4("MELensRoomCut", RV.roomNormal, RV.roomDebug ? 1f : 0f, windows, RV.windowDark);
            // (the camper's body only: the dark jambs of its doors are painted like the room)
            int jambs = isCut && !furniture && RV.doorPaintEnabled && isBody(slot, inst) ? RV.jambCount : 0;
            program.setVector4("MELensJambCount", jambs, 0f, 0f, 0f);
            if (jambs > 0) {
                int location = jambLocation(program);
                if (location >= 0) {
                    GL20.glUniform3fv(location, RV.jambUpload);
                }
            }
            if (windows > 0) {
                int location = windowLocation(program);
                if (location >= 0) {
                    GL20.glUniform3fv(location, RV.windowUpload);
                }
            }
            if (room) {
                int location = ringLocation(program);
                if (location >= 0) {
                    GL20.glUniform2fv(location, RV.roomUpload);
                }
            }
        }
        float[] clip0 = RV.clipBoxes[0];
        float[] clip1 = RV.clipBoxes[1];
        program.setVector3("MELensClipMin0", clip0[0], clip0[1], clip0[2]);
        program.setVector3("MELensClipMax0", clip0[3], clip0[4], clip0[5]);
        program.setVector3("MELensClipMin1", clip1[0], clip1[1], clip1[2]);
        program.setVector3("MELensClipMax1", clip1[3], clip1[4], clip1[5]);
        if (lightMode == 1f && diagnostics.getAndIncrement() % 600 == 0) {
            lastLightDraw = modelName(inst)
                    + " toBody=" + (program.getUniform("MELensToBody", 35676) != null)
                    + " lamp0=" + (program.getUniform("MELensLamp0", 35666) != null)
                    + " colour=" + (program.getUniform("MELensLampColour", 35665) != null)
                    + " fill=" + (program.getUniform("MELensFill", 35666) != null)
                    + " scratch=" + scratch.m30() + "," + scratch.m31() + "," + scratch.m32() + " scale=" + scratch.m00()
                    + " mesh=" + model.mesh.minXyz + ".." + model.mesh.maxXyz;
        }
        model.effect = cut;
        swappedModel.set(model);
        originalShader.set(original);
        cutDraws.incrementAndGet();
        return false;
    }

    /** Diagnostics: each sub-model of the cut camper, its mesh bounds and its transform into the body's mesh space. */
    static final java.util.Map<String, String> surveyed = new java.util.concurrent.ConcurrentHashMap<>();

    private static void survey(Model model, ModelInstanceRenderData inst, Matrix4f body) {
        String name = modelName(inst);
        if (name.isEmpty()) {
            name = "(unnamed " + System.identityHashCode(model) + ")";
        }
        name += " [mesh:" + meshName(inst) + "]";
        Matrix4f toBody = new Matrix4f(body).invert().mul(inst.xfrm);
        org.joml.Vector3f lo = new org.joml.Vector3f(model.mesh.minXyz.x, model.mesh.minXyz.y, model.mesh.minXyz.z);
        org.joml.Vector3f hi = new org.joml.Vector3f(model.mesh.maxXyz.x, model.mesh.maxXyz.y, model.mesh.maxXyz.z);
        org.joml.Vector3f bodyLo = toBody.transformPosition(new org.joml.Vector3f(lo));
        org.joml.Vector3f bodyHi = toBody.transformPosition(new org.joml.Vector3f(hi));
        surveyed.put(name, "mesh " + lo + ".." + hi + " -> body " + bodyLo + ".." + bodyHi
                + " scale " + toBody.getScale(new org.joml.Vector3f())
                + " shader=" + (model.effect == null ? "none" : model.effect.getName())
                + " wheel=" + (inst.modelInstance instanceof zombie.core.skinnedmodel.model.VehicleSubModelInstance sub
                    && sub.modelInfo != null && sub.modelInfo.part != null ? sub.modelInfo.part.getWheelIndex() : -1));
    }

    public static void endVehicleDraw(ModelSlotRenderData slot, ModelInstanceRenderData inst) {
        endVehicleDraw();
        if (ViewpointCompat.active()) {
            return;
        }
        // the depth the game gave the camper's models this draw (see alignCabinDepth)
        Object vehicle = RV.cutVehicle;
        if (vehicle != null && slot != null && slot.object == vehicle && inst != null && inst.modelInstance != null) {
            depthVehicle = vehicle;
            vehicleDepth = inst.modelInstance.targetDepth;
        }
    }

    public static void endVehicleDraw() {
        Model model = swappedModel.get();
        if (model == null) {
            return;
        }
        model.effect = originalShader.get();
        swappedModel.remove();
        originalShader.remove();
    }

    /** The camper you are in and the model depth the game gave its models (ModelInstance.targetDepth). */
    private static volatile Object depthVehicle;
    private static volatile float vehicleDepth;

    /** The depth a passenger inside {@code vehicle} is drawn in this frame (see {@link #alignCabinDepth}), or NaN. */
    static float cabinDepth(Object vehicle) {
        return vehicle != null && depthVehicle == vehicle ? vehicleDepth - 1.0E-4f : Float.NaN;
    }

    /**
     * Characters inside the camper you are in are drawn in the camper's depth. The game
     * places a passenger's model depth by the passenger's own square, which in a long
     * vehicle lies tiles from the vehicle's, so the camper's furniture hid a passenger
     * sitting in front of it (and could show through one standing behind it). With the
     * camper's depth, the two sort by where they really are. A zombie beside the camper gets
     * the same treatment by its side (see {@link #zombieSide}): the game's depth by its square
     * drew a zombie on the far side of a long camper in front of all of it.
     */
    public static void alignCabinDepth(ModelSlotRenderData slot, ModelInstanceRenderData inst) {
        if (ViewpointCompat.active()) {
            return;
        }
        Object vehicle = depthVehicle;
        if (vehicle == null || vehicle != RV.cutVehicle || slot == null || inst == null || inst.modelInstance == null) {
            return;
        }
        IsoGameCharacter character = slot.character;
        if (character == null) {
            return;
        }
        float depth;
        if (character.getVehicle() == vehicle) {
            // the game keeps a character a hair in front of what it touches
            depth = vehicleDepth - 1.0E-4f;
        } else if (RV.zombieDepthEnabled && character instanceof IsoZombie) {
            int side = zombieSide((BaseVehicle) vehicle, slot.x, slot.y);
            if (side == 0) {
                return;
            }
            depth = side < 0 ? vehicleDepth + 1.0E-4f : vehicleDepth - 1.0E-4f;
        } else {
            return;
        }
        inst.modelInstance.targetDepth = depth;
        if (inst.modelInstance.parent != null) {
            inst.modelInstance.parent.targetDepth = depth;
        }
        if (slot.modelSlot != null && slot.modelSlot.model != null) {
            slot.modelSlot.model.targetDepth = depth;
        }
    }

    /** How far behind the camper (tiles, along the direction to the camera) a zombie is still sorted behind it. */
    private static final float BEHIND_REACH = 3.0f;
    /** How close to the camper (tiles) a zombie not behind it is sorted in front of it. */
    private static final float BESIDE_REACH = 1.6f;

    /**
     * Which side of the camper a zombie is on, as the camera sees it: -1 with the camper between the zombie and the
     * camera (the camera looks along world (-x, -y), so the point towards it lies at (+x, +y)), +1 beside it or in
     * front of it, 0 when it is too far to matter (the game's own depth stays).
     */
    static int zombieSide(BaseVehicle vehicle, float x, float y) {
        try {
            if (Math.abs(x - vehicle.getX()) > 8.0f || Math.abs(y - vehicle.getY()) > 8.0f) {
                return 0;
            }
            for (float t = 0.3f; t <= BEHIND_REACH; t += 0.3f) {
                float d = t * 0.7071f;
                if (vehicle.isInBounds(x + d, y + d)) {
                    return -1;
                }
            }
            for (int k = 0; k < 8; k++) {
                double a = k * Math.PI / 4;
                float dx = (float) Math.cos(a) * BESIDE_REACH;
                float dy = (float) Math.sin(a) * BESIDE_REACH;
                if (vehicle.isInBounds(x + dx, y + dy)) {
                    return 1;
                }
            }
        } catch (RuntimeException e) {
            // never break the game's drawing over this
        }
        return 0;
    }

    public static void orientCabinCharacter(ModelSlotRenderData slot) {
        if (ViewpointCompat.active()) {
            return;
        }
        if (slot == null || !slot.inVehicle || slot.character == null) {
            return;
        }
        Float radians = RV.facing.get(slot.character);
        if (radians == null) {
            return;
        }
        facingCalls.incrementAndGet();
        Core.getInstance().modelViewMatrixStack.peek().rotateY(radians);
    }

    /** The static furniture shader, for what {@link Loose} draws itself; null when it did not compile. */
    static Shader partStaticShader() {
        return shader(PART_SHADER, true, false);
    }

    static Matrix4f bodyTransformOf(ModelSlotRenderData slot) {
        return bodyTransform(slot);
    }

    private static Matrix4f bodyTransform(ModelSlotRenderData slot) {
        ModelManager.ModelSlot modelSlot = slot.modelSlot;
        ModelInstance main = modelSlot == null ? null : modelSlot.model;
        if (main == null) {
            return null;
        }
        for (int i = 0; i < slot.modelData.size(); i++) {
            ModelInstanceRenderData data = slot.modelData.get(i);
            if (data.modelInstance == main) {
                return data.xfrm;
            }
        }
        return null;
    }

    /**
     * The model script name of a sub-model, "" when it has none: other mods' vehicles have
     * unnamed model scripts (KI5's '87 Ford B700), and every vehicle drawn passes here.
     */
    private static String modelName(ModelInstanceRenderData inst) {
        ModelScript script = inst.modelInstance == null ? null : inst.modelInstance.modelScript;
        String name = script == null ? null : script.getName();
        return name == null ? "" : name;
    }

    /**
     * The FBX object a sub-model draws ("b700_interior_bus" for
     * "vehicles/Vehicles_87fordB700_Body|b700_interior_bus"), "" when unknown.
     */
    private static String meshName(ModelInstanceRenderData inst) {
        Model model = inst.modelInstance == null ? null : inst.modelInstance.model;
        if (model == null) {
            return "";
        }
        String mesh = model.assetParams == null ? null : model.assetParams.meshName;
        if (mesh == null && model.mesh != null && model.mesh.getPath() != null) {
            mesh = model.mesh.getPath().getPath();
        }
        if (mesh == null) {
            return "";
        }
        int bar = mesh.lastIndexOf('|');
        return bar >= 0 ? mesh.substring(bar + 1) : mesh;
    }

    /**
     * The plane that removes part of a sub-model, by its model script name, or for a
     * sub-model drawn without one (KI5's bus interior) by "mesh:" + its FBX object.
     */
    private static float[] keepPlaneFor(ModelInstanceRenderData inst, java.util.Map<String, float[]> planes) {
        if (planes.isEmpty()) {
            return null;
        }
        float[] plane = planes.get(modelName(inst));
        if (plane == null) {
            String mesh = meshName(inst);
            if (!mesh.isEmpty()) {
                plane = planes.get("mesh:" + mesh);
            }
        }
        return plane;
    }

    /** ME: LENS' inside: the shells (MELensShell*) and the furniture and decor (MELensRV_*). */
    private static boolean isOwnInside(ModelInstanceRenderData inst) {
        return modelName(inst).startsWith("MELens");
    }

    private static final RV.Marker[] NO_SPOTS = new RV.Marker[0];
    private static final String[] SPOT = new String[RV.MAX_SPOTS];
    private static final String[] SPOT_SIZE = new String[RV.MAX_SPOTS];
    private static final String[] SPOT_COLOUR = new String[RV.MAX_SPOTS];
    static {
        for (int i = 0; i < RV.MAX_SPOTS; i++) {
            SPOT[i] = "MELensSpot[" + i + "]";
            SPOT_SIZE[i] = "MELensSpotSize[" + i + "]";
            SPOT_COLOUR[i] = "MELensSpotColour[" + i + "]";
        }
    }

    /**
     * Locations of the floor-highlight array elements per shader program: the game only
     * knows an array uniform by its first element's name.
     */
    private static final java.util.Map<Integer, int[][]> spotLocationsByProgram = new java.util.concurrent.ConcurrentHashMap<>();

    private static int[][] spotLocations(ShaderProgram program) {
        return spotLocationsByProgram.computeIfAbsent(program.getShaderID(), id -> {
            int[][] locations = new int[3][RV.MAX_SPOTS];
            for (int i = 0; i < RV.MAX_SPOTS; i++) {
                locations[0][i] = GL20.glGetUniformLocation(id, SPOT[i]);
                locations[1][i] = GL20.glGetUniformLocation(id, SPOT_SIZE[i]);
                locations[2][i] = GL20.glGetUniformLocation(id, SPOT_COLOUR[i]);
            }
            return locations;
        });
    }

    /** Where the room's outline array starts, per shader program (an array uniform is known by its first element). */
    private static final java.util.Map<Integer, Integer> ringLocationByProgram = new java.util.concurrent.ConcurrentHashMap<>();

    private static int ringLocation(ShaderProgram program) {
        return ringLocationByProgram.computeIfAbsent(program.getShaderID(),
                id -> GL20.glGetUniformLocation(id, "MELensRing[0]"));
    }

    /** Where the window boxes array starts, per shader program. */
    private static final java.util.Map<Integer, Integer> windowLocationByProgram = new java.util.concurrent.ConcurrentHashMap<>();

    private static int windowLocation(ShaderProgram program) {
        return windowLocationByProgram.computeIfAbsent(program.getShaderID(),
                id -> GL20.glGetUniformLocation(id, "MELensWin[0]"));
    }

    /** Where the door jamb boxes array starts, per shader program. */
    private static final java.util.Map<Integer, Integer> jambLocationByProgram = new java.util.concurrent.ConcurrentHashMap<>();

    private static int jambLocation(ShaderProgram program) {
        return jambLocationByProgram.computeIfAbsent(program.getShaderID(),
                id -> GL20.glGetUniformLocation(id, "MELensJamb[0]"));
    }

    /** The actual vehicle body, including stock meshes and named KI5 body variants. */
    private static boolean isBody(ModelSlotRenderData slot, ModelInstanceRenderData inst) {
        return slot.modelSlot != null && slot.modelSlot.model == inst.modelInstance;
    }

    /** A door leaf: KI5 names its FBX object "..._door_..." (a truck's rear door "..._trunkDoor"). */
    private static boolean isDoor(ModelInstanceRenderData inst) {
        String mesh = meshName(inst).toLowerCase(java.util.Locale.ROOT);
        return mesh.contains("door") && !mesh.contains("trunk");
    }

    /** The shell's walls: ME: LENS' inside lining (MELensShell_*_walls). */
    private static boolean isShellWalls(ModelInstanceRenderData inst) {
        String name = modelName(inst);
        return name.startsWith("MELensShell_") && (name.endsWith("_walls") || name.endsWith("_bulkhead") || name.endsWith("_entry"));
    }

    private static boolean isCabBulkhead(ModelInstanceRenderData inst) {
        String name = modelName(inst);
        return name.startsWith("MELensShell_") && name.endsWith("_bulkhead");
    }

    /** A piece's preview while you place furniture: its ghost model (MELensRV_*_ghost). */
    private static boolean isGhost(ModelInstanceRenderData inst) {
        return modelName(inst).endsWith("_ghost");
    }

    /** RV furniture models are named MELensRV_*. */
    private static boolean isFurniture(ModelInstanceRenderData inst) {
        return modelName(inst).startsWith("MELensRV_");
    }

    /**
     * How the interior light applies to one sub-model: 1 for the camper's interior models
     * (every face), 2 for the shell, doors and windows (only faces looking into the camper;
     * the shader's footprint test needs a body whose up axis is z), 0 for everything else
     * (wheels, awning, jack, tanks).
     */
    private static float lightMode(ModelInstanceRenderData inst, Shader original, RV.Light light) {
        if (light.interiorModels().contains(modelName(inst))) {
            return 1f;
        }
        boolean zUp = Math.abs(RV.planeC) >= Math.max(Math.abs(RV.planeA), Math.abs(RV.planeB));
        return original.isVehicleShader() && zUp ? 2f : 0f;
    }

    private static boolean entirelyBelow(ModelMesh mesh, Vector4f p) {
        if (mesh == null || mesh.minXyz.x > mesh.maxXyz.x) {
            return false;
        }
        for (int corner = 0; corner < 8; corner++) {
            float x = (corner & 1) == 0 ? mesh.minXyz.x : mesh.maxXyz.x;
            float y = (corner & 2) == 0 ? mesh.minXyz.y : mesh.maxXyz.y;
            float z = (corner & 4) == 0 ? mesh.minXyz.z : mesh.maxXyz.z;
            if (p.x * x + p.y * y + p.z * z + p.w > 0.0f) {
                return false;
            }
        }
        return true;
    }

    private static Shader shader(String name, boolean isStatic, boolean mustBeVehicleShader) {
        if (retry) {
            retry = false;
            for (int i = 0; i < failed.length; i++) {
                failed[i] = false;
            }
            shaderError = null;
        }
        int key = (name.equals(VEHICLE_SHADER) ? 0 : 2) + (isStatic ? 0 : 1);
        Shader shader = shaders[key];
        if (shader != null) {
            return shader;
        }
        if (failed[key]) {
            return null;
        }
        String label = name + (isStatic ? "_static" : "");
        try {
            shader = ShaderManager.instance.getOrCreateShader(name, isStatic, false);
        } catch (RuntimeException | LinkageError failure) {
            fail(key, label + ": " + failure);
            return null;
        }
        if (shader == null || shader.getShaderProgram() == null || !shader.getShaderProgram().isCompiled()) {
            fail(key, label + " did not compile; see console.txt");
            return null;
        }
        if (mustBeVehicleShader && !shader.isVehicleShader()) {
            fail(key, label + " lost its vehicle texture inputs");
            return null;
        }
        shaders[key] = shader;
        return shader;
    }

    private static void fail(int key, String message) {
        failed[key] = true;
        shaderError = message;
        System.err.println("[ME_LENS] cutaway shader unavailable, drawing the normal camper instead: " + message);
    }
}
