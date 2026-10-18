package me.lens.rv;

import java.util.ArrayList;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;
import zombie.core.Core;
import zombie.core.ImmutableColor;
import zombie.core.PerformanceSettings;
import zombie.core.opengl.PZGLUtil;
import zombie.core.opengl.ShaderProgram;
import zombie.core.skinnedmodel.ModelCamera;
import zombie.core.skinnedmodel.ModelManager;
import zombie.core.skinnedmodel.model.ItemModelRenderer;
import zombie.core.skinnedmodel.model.Model;
import zombie.core.skinnedmodel.model.ModelInstance;
import zombie.core.skinnedmodel.model.ModelInstanceRenderData;
import zombie.core.skinnedmodel.model.ModelMesh;
import zombie.core.skinnedmodel.model.ModelSlotRenderData;
import zombie.core.skinnedmodel.model.VertexBufferObject;
import zombie.core.skinnedmodel.population.ClothingItem;
import zombie.core.skinnedmodel.shader.Shader;
import zombie.core.skinnedmodel.visual.ItemVisual;
import zombie.core.textures.Texture;
import zombie.inventory.InventoryItem;
import zombie.inventory.types.Clothing;
import zombie.inventory.types.HandWeapon;
import zombie.scripting.ScriptManager;
import zombie.scripting.objects.ModelAttachment;
import zombie.scripting.objects.ModelScript;

/**
 * Loose items: what you place or drop inside a vehicle, drawn as the 3D model the game itself uses for
 * an item lying on the ground (a flat picture of its icon when it has none), but inside the one vehicle
 * you are in.
 *
 * The game draws a world item against the depth of its map square, which inside a long vehicle puts it in
 * front of or behind the whole vehicle. Here the item is drawn in the vehicle's own depth, right after the
 * vehicle's last sub-model, with the furniture shader (so it gets the interior light, is never cut away and
 * is hidden by walls and furniture in front of it).
 *
 * Lua (main thread) builds the list ({@link #begin}, {@link #add}, {@link #end}); the render thread only
 * reads the published immutable array.
 */
public final class Loose {
    /** One thing to draw. Immutable once published. */
    static final class Entry {
        final ModelMesh mesh;
        final Texture texture;
        /** Item mesh space to the camper body's mesh space (also what the shader's lamps and clip boxes work in). */
        final Matrix4f toBody;
        final float red, green, blue;
        final boolean ghost, valid;
        /** Where the texture's picture lies in its page: u, v, width, height (a flat icon is a part of an atlas). */
        final float[] uv;
        /** Set by the render thread when drawing this entry threw: it is skipped from then on (the others go on). */
        volatile boolean broken;

        Entry(ModelMesh mesh, Texture texture, float[] uv, Matrix4f toBody, float red, float green, float blue,
                boolean ghost, boolean valid) {
            this.mesh = mesh;
            this.texture = texture;
            this.uv = uv;
            this.toBody = toBody;
            this.red = red;
            this.green = green;
            this.blue = blue;
            this.ghost = ghost;
            this.valid = valid;
        }
    }

    /** A model resolved for an item type: the mesh and how it sits on a surface. */
    private static final class Resolved {
        final Model model;
        final Texture texture;
        final float[] uv;
        /** Item mesh to the item frame (tiles), centred over the origin and resting on y = 0. */
        final Matrix4f rest;
        final float sizeX, sizeY, sizeZ;

        Resolved(Model model, Texture texture, float[] uv, Matrix4f rest, float sizeX, float sizeY, float sizeZ) {
            this.model = model;
            this.texture = texture;
            this.uv = uv;
            this.rest = rest;
            this.sizeX = sizeX;
            this.sizeY = sizeY;
            this.sizeZ = sizeZ;
        }
    }

    /** Passenger space to the body's mesh space: x = -px / scale, y = pz / scale, z = lift - py / scale. */
    static volatile float scale = 0.09f;
    static volatile float lift = 0.666f;
    /**
     * The game draws items through its iso camera, which scales models by 1.5 (Core.DoPushIsoStuff for anything
     * that is not a vehicle); a vehicle's camera does not. Items inside a vehicle get that factor themselves.
     */
    static volatile float tileScale = 1.5f;
    /** The most items drawn at once. */
    static volatile int limit = 64;
    /** An item rests this far (tiles) above its surface, as the game lifts a ground item to keep it off the floor. */
    static final float REST_LIFT = 0.004f;
    /** An icon lying flat is this wide (tiles) for the game's default world icon size. */
    static final float ICON_WIDTH = 0.26f;
    private static final float[] WHOLE = {0.0f, 0.0f, 1.0f, 1.0f};

    private static final Entry[] NONE = new Entry[0];

    static volatile Entry[] entries = NONE;
    static volatile Entry ghost;
    /** The vehicle the published list belongs to: nothing is drawn in another one (a stale list never follows you in). */
    static volatile Object owner;
    static volatile String lastError;
    /** Render-thread CPU time of the loose items' draw calls per frame (microseconds, running average). */
    static volatile double averageMicros;
    static final java.util.concurrent.atomic.AtomicLong drawn = new java.util.concurrent.atomic.AtomicLong();

    private static final ArrayList<Entry> pending = new ArrayList<>();
    private static final Map<String, Resolved> cache = new ConcurrentHashMap<>();
    private static volatile boolean disabled;
    private static volatile long disabledAt;
    private static int reported;

    // render thread only
    private static final Matrix4f IDENTITY = new Matrix4f();
    private static final Matrix4f placed = new Matrix4f();

    private Loose() {}

    // ------------------------------------------------------------------ main thread: resolving

    /** Whether the game draws this item as a 3D model when it lies on the ground. */
    static boolean supported(InventoryItem item) {
        if (item == null) {
            return false;
        }
        try {
            return ItemModelRenderer.itemHasModel(item) && modelScript(item) != null;
        } catch (RuntimeException failure) {
            return false;
        }
    }

    /** Whether it can be shown at all: as its model, or as a flat picture of its icon. */
    static boolean showable(InventoryItem item) {
        return item != null && (supported(item) || item.getTex() != null);
    }

    private static ModelScript modelScript(InventoryItem item) {
        String name = item.getWorldStaticItem();
        if (name != null && !name.isEmpty()) {
            return ScriptManager.instance.getModelScript(name);
        }
        if (item instanceof HandWeapon) {
            String weapon = item.getStaticModel();
            return weapon == null || weapon.isEmpty() ? null : ScriptManager.instance.getModelScript(weapon);
        }
        return null;
    }

    private static boolean modelReady(Model model) {
        return model != null && !model.isFailure() && model.isReady() && model.mesh != null && model.mesh.isReady()
                && model.isStatic;
    }

    /**
     * The model of an item, loading it if it is not loaded yet; null while it loads. {@code textureName} is the
     * texture a placed item was seen with (a bag keeps the colour it has), or null for the item's own.
     */
    private static Resolved resolve(InventoryItem item, String textureName) {
        ModelScript script = modelScript(item);
        if (script == null) {
            return decal(item);
        }
        String meshName = script.getMeshName();
        String texName = script.getTextureName();
        String shaderName = script.getShaderName();
        boolean isStatic = script.isStatic;
        ClothingItem clothing = item.getClothingItem();
        if (item instanceof Clothing || clothing != null) {
            // as ItemModelRenderer.renderMain: a bag or hat takes its texture from its visual
            texName = script.getTextureName(true);
            if (texName == null) {
                ItemVisual visual = item.getVisual();
                if (textureName != null && !textureName.isEmpty()) {
                    texName = textureName;
                } else if (visual != null && clothing != null) {
                    texName = clothing.textureChoices.isEmpty() ? visual.getBaseTexture(clothing) : visual.getTextureChoice(clothing);
                }
            }
        }
        if (texName == null) {
            return decal(item);
        }
        String key = script.getName() + "|" + texName + "|" + item.worldScale + "|" + (item instanceof HandWeapon);
        Resolved known = cache.get(key);
        if (known != null) {
            return known;
        }
        ModelManager models = ModelManager.instance;
        Model model = models.tryGetLoadedModel(meshName, texName, isStatic, shaderName, false);
        if (model == null) {
            models.loadAdditionalModel(meshName, texName, isStatic, shaderName);
            model = models.tryGetLoadedModel(meshName, texName, isStatic, shaderName, false);
        }
        if (!modelReady(model) || model.tex == null || !model.tex.isReady()) {
            return null;
        }
        // The game's own transform for a world item (ItemModelRenderer.init): the model script's "world"
        // attachment moved to the origin, the mesh's own transform, then the script's scale.
        Matrix4f tiles = new Matrix4f();
        tiles.scale(tileScale);
        if (item instanceof HandWeapon) {
            tiles.rotateXYZ(0.0f, (float) Math.PI, 1.5707964f);
        }
        ModelAttachment world = script.getAttachmentById("world");
        if (world != null) {
            Matrix4f attachment = new Matrix4f();
            ModelInstanceRenderData.makeAttachmentTransform(world, attachment);
            attachment.invert();
            tiles.mul(attachment);
        }
        if (model.mesh.transform != null) {
            Matrix4f mesh = new Matrix4f(model.mesh.transform);
            mesh.transpose();
            tiles.mul(mesh);
        }
        float itemScale = script.scale * item.worldScale;
        if (itemScale != 1.0f) {
            tiles.scale(itemScale);
        }
        Resolved resolved = resting(model, model.tex, WHOLE, tiles);
        cache.put(key, resolved);
        return resolved;
    }

    /** A flat picture of the item's icon, for an item the game has no model for. */
    private static Resolved decal(InventoryItem item) {
        Texture icon = item.getTex();
        if (icon == null || !icon.isReady()) {
            return null;
        }
        ModelManager models = ModelManager.instance;
        Model model = ScriptManager.instance.getModelScript("MELensDecal") == null ? null : models.getLoadedModel("MELensDecal");
        if (!modelReady(model)) {
            return null;
        }
        // the quad is one tile wide, lying in the mesh's x-z plane
        Vector3f lo = model.mesh.minXyz;
        Vector3f hi = model.mesh.maxXyz;
        float meshWidth = Math.max(hi.x - lo.x, 1.0e-4f);
        float width = ICON_WIDTH;
        if (item.getScriptItem() != null) {
            width *= Math.max(item.getScriptItem().scaleWorldIcon, 0.25f);
        }
        float aspect = icon.getHeightOrig() > 0 ? (float) icon.getWidthOrig() / (float) icon.getHeightOrig() : 1.0f;
        Matrix4f tiles = new Matrix4f().scale(width / meshWidth, 1.0f, width / meshWidth / Math.max(aspect, 0.1f));
        float[] uv = {icon.getXStart(), icon.getYStart(), icon.getXEnd() - icon.getXStart(), icon.getYEnd() - icon.getYStart()};
        return resting(model, icon, uv, tiles);
    }

    /** Centres a mesh transformed by {@code tiles} over the origin with its underside on y = 0. */
    private static Resolved resting(Model model, Texture texture, float[] uv, Matrix4f tiles) {
        Vector3f lo = model.mesh.minXyz;
        Vector3f hi = model.mesh.maxXyz;
        float minX = Float.MAX_VALUE, minY = Float.MAX_VALUE, minZ = Float.MAX_VALUE;
        float maxX = -Float.MAX_VALUE, maxY = -Float.MAX_VALUE, maxZ = -Float.MAX_VALUE;
        Vector3f corner = new Vector3f();
        for (int i = 0; i < 8; i++) {
            corner.set((i & 1) == 0 ? lo.x : hi.x, (i & 2) == 0 ? lo.y : hi.y, (i & 4) == 0 ? lo.z : hi.z);
            tiles.transformPosition(corner);
            minX = Math.min(minX, corner.x);
            maxX = Math.max(maxX, corner.x);
            minY = Math.min(minY, corner.y);
            maxY = Math.max(maxY, corner.y);
            minZ = Math.min(minZ, corner.z);
            maxZ = Math.max(maxZ, corner.z);
        }
        Matrix4f rest = new Matrix4f().translation(-(minX + maxX) / 2, -minY + REST_LIFT, -(minZ + maxZ) / 2).mul(tiles);
        return new Resolved(model, texture, uv, rest, maxX - minX, Math.max(maxY - minY, 0.01f), maxZ - minZ);
    }

    /**
     * The item's size in tiles along the vehicle's axes at yaw 0 ("left,up,front"), or null while its model loads
     * or when it has none.
     */
    static String size(InventoryItem item, String textureName) {
        Resolved resolved = item == null ? null : resolve(item, textureName);
        if (resolved == null) {
            return null;
        }
        // item frame x runs to the vehicle's front, z to its left (see entry)
        return String.format(java.util.Locale.ROOT, "%.4f,%.4f,%.4f", resolved.sizeZ, resolved.sizeY, resolved.sizeX);
    }

    static void begin(Object vehicle) {
        pending.clear();
        owner = vehicle;
    }

    /**
     * Adds an item standing at a passenger-space point ({@code x} to the vehicle's left, {@code y} up, {@code z}
     * to its front, tiles) turned {@code yawDegrees}. {@code textureName} and the tint are how it looks if it is not
     * how a new item of its type does (null, and a negative red). False while its model is still loading.
     */
    static boolean add(InventoryItem item, double x, double y, double z, double yawDegrees, String textureName,
            double red, double green, double blue, boolean asGhost, boolean valid) {
        Resolved resolved = item == null ? null : resolve(item, textureName);
        if (resolved == null) {
            return false;
        }
        Entry entry = entry(resolved, item, x, y, z, yawDegrees, red, green, blue, asGhost, valid);
        if (asGhost) {
            ghost = entry;
        } else if (pending.size() < limit) {
            pending.add(entry);
        }
        return true;
    }

    private static Entry entry(Resolved resolved, InventoryItem item, double x, double y, double z, double yawDegrees,
            double red, double green, double blue, boolean asGhost, boolean valid) {
        float s = scale;
        float inverse = 1.0f / s;
        // the item frame is the game's own for a world item (its x to the front, y up, z to the left of
        // an east-facing vehicle), in tiles; the body's mesh space has its x mirrored, y to the front and z down
        Matrix4f toBody = new Matrix4f().translation((float) (-x * inverse), (float) (z * inverse), lift - (float) (y * inverse));
        Matrix4f axes = new Matrix4f(
                0.0f, inverse, 0.0f, 0.0f,
                0.0f, 0.0f, -inverse, 0.0f,
                -inverse, 0.0f, 0.0f, 0.0f,
                0.0f, 0.0f, 0.0f, 1.0f);
        toBody.mul(axes).rotateY((float) Math.toRadians(yawDegrees)).mul(resolved.rest);
        float r, g, b;
        if (red >= 0.0) {
            r = (float) red;
            g = (float) green;
            b = (float) blue;
        } else {
            float[] tint = tintOf(item);
            r = tint[0];
            g = tint[1];
            b = tint[2];
        }
        Model model = resolved.model;
        return new Entry(model.mesh, resolved.texture, resolved.uv, toBody, r, g, b, asGhost, valid);
    }

    /** The item's tint as the game draws a world item: a bag's or hat's from its visual, else its own colour. */
    private static float[] tintOf(InventoryItem item) {
        ClothingItem clothing = item.getClothingItem();
        if ((item instanceof Clothing || clothing != null) && !item.isCustomColor()) {
            ItemVisual visual = item.getVisual();
            if (visual != null && clothing != null) {
                ImmutableColor tint = visual.getTint(clothing);
                return new float[] {tint.r, tint.g, tint.b};
            }
        }
        return new float[] {item.getColorRed(), item.getColorGreen(), item.getColorBlue()};
    }

    static void end() {
        entries = pending.toArray(new Entry[0]);
    }

    static void clear() {
        entries = new Entry[0];
        ghost = null;
        owner = null;
        pending.clear();
    }

    static void clearCache() {
        cache.clear();
    }

    static void clearGhost() {
        ghost = null;
    }

    // ------------------------------------------------------------------ render thread

    /**
     * After each sub-model of a vehicle is drawn: after the last one of the camper you are in, the loose items.
     * Public because the patch's advice is inlined into the game's own class.
     */
    public static void afterModel(ModelInstanceRenderData inst, ModelSlotRenderData slot) {
        if (slot == null || slot.object == null || slot.object != RV.cutVehicle || slot.renderToTexture) {
            return;
        }
        if (disabled) {
            // a failure that was not one entry's: try again every half minute (and when Lua asks, on entering a vehicle)
            if (System.currentTimeMillis() - disabledAt < 30000L) {
                return;
            }
            disabled = false;
        }
        Entry[] list = entries;
        Entry preview = ghost;
        Object belongsTo = owner;
        if (belongsTo != null && belongsTo != slot.object) {
            list = NONE;                               // published for another vehicle: not these
        }
        if (list.length == 0 && preview == null) {
            return;
        }
        int last = slot.modelData.size() - 1;
        if (last < 0 || slot.modelData.get(last) != inst) {
            return;
        }
        try {
            long start = System.nanoTime();
            draw(slot, list, preview);
            // CPU time the draw calls take on the render thread, as a running average (microseconds)
            long micros = (System.nanoTime() - start) / 1000L;
            averageMicros += (micros - averageMicros) * 0.05;
        } catch (Throwable failure) {
            disabled = true;
            disabledAt = System.currentTimeMillis();
            lastError = failure.toString();
            if (reported++ < 3) {
                System.err.println("[ME_LENS] loose items are not drawn (trying again later): " + failure);
                failure.printStackTrace();
            }
        }
    }

    private static void draw(ModelSlotRenderData slot, Entry[] list, Entry preview) {
        Matrix4f body = Cutaway.bodyTransformOf(slot);
        Shader shader = Cutaway.partStaticShader();
        if (body == null || shader == null) {
            return;
        }
        ModelCamera camera = ModelCamera.instance;
        if (camera == null) {
            return;
        }
        GL11.glDisable(2884);          // a world item is drawn with both faces
        boolean begun = false, started = false;
        try {
            GL11.glEnable(2929);
            GL11.glDepthFunc(513);
            camera.Begin();
            begun = true;
            Core.getInstance().modelViewMatrixStack.peek().translate(0.0f, slot.centerOfMassY, 0.0f);
            float depth = 0.5f;
            if (PerformanceSettings.fboRenderChunk) {
                depth = slot.squareDepth - (VertexBufferObject.getDepthValueAt(0.0f, 0.0f, 0.0f) + 1.0f) / 2.0f + 0.5f;
            }
            shader.Start();
            started = true;
            ShaderProgram program = shader.getShaderProgram();
            constants(shader, program, slot, depth);
            for (Entry entry : list) {
                drawEntry(shader, program, body, entry);
            }
            if (preview != null) {
                drawEntry(shader, program, body, preview);
            }
            drawn.addAndGet(list.length + (preview == null ? 0 : 1));
        } finally {
            if (started) {
                shader.End();
            }
            if (begun) {
                camera.End();
            }
            GL11.glEnable(2884);
        }
    }

    /** One entry; if it throws, it is marked and left out from then on, the others are drawn as before. */
    private static void drawEntry(Shader shader, ShaderProgram program, Matrix4f body, Entry entry) {
        if (entry.broken) {
            return;
        }
        try {
            drawOne(shader, program, body, entry);
        } catch (RuntimeException failure) {
            entry.broken = true;
            lastError = failure.toString();
            if (reported++ < 3) {
                System.err.println("[ME_LENS] a loose item is not drawn: " + failure);
                failure.printStackTrace();
            }
        }
    }

    /** Everything that is the same for every item of this frame, as for the furniture sub-models. */
    private static void constants(Shader shader, ShaderProgram program, ModelSlotRenderData slot, float depth) {
        // the vehicle's lights, as Model.setLights hands them to a sub-model
        ModelInstance.EffectLight[] lights = slot.effectLights;
        for (int i = 0; i < lights.length; i++) {
            ModelInstance.EffectLight el = lights[i];
            shader.setLight(i, el.x, el.y, el.z, el.r, el.g, el.b, el.radius, slot.animPlayerAngle, slot.x, slot.y, slot.z, slot.object);
        }
        for (int i = lights.length; i < 5; i++) {
            shader.setLight(i, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, null);
        }
        shader.setAmbient(slot.ambientR, slot.ambientG, slot.ambientB);
        shader.setTargetDepth(depth);
        shader.setShaderAlpha(slot.alpha);
        shader.setTransformMatrix(IDENTITY, false);

        program.setVector4("MELensBodyPlane", 0f, 0f, 0f, -1.0f);
        program.setVector4("MELensNearCut", 0f, 0f, 0f, 0f);
        program.setVector4("MELensCutFront", 0f, 0f, 0f, 0f);
        program.setVector4("MELensKeepPlane", 0f, 0f, 0f, -1.0f);
        program.setVector4("MELensBodyUp", RV.planeA, RV.planeB, RV.planeC, 1f);
        ModelMesh bodyMesh = slot.modelSlot.model.model == null ? null : slot.modelSlot.model.model.mesh;
        if (bodyMesh != null && bodyMesh.minXyz.x <= bodyMesh.maxXyz.x) {
            program.setVector4("MELensShape", bodyMesh.minXyz.x, bodyMesh.minXyz.y, bodyMesh.maxXyz.x, bodyMesh.maxXyz.y);
        } else {
            program.setVector4("MELensShape", 0f, 0f, 0f, 0f);
        }
        RV.Light light = RV.light;
        program.setVector4("MELensFill", light.share(), light.constant(), light.bias(), 0f);
        float[] lamp0 = light.lamp0();
        float[] lamp1 = light.lamp1();
        program.setVector4("MELensLamp0", lamp0[0], lamp0[1], lamp0[2], lamp0[3]);
        program.setVector4("MELensLamp1", lamp1[0], lamp1[1], lamp1[2], lamp1[3]);
        program.setVector3("MELensLampColour", light.red(), light.green(), light.blue());
        program.setVector4("MELensMarker", 0f, 0f, 0f, 0f);        // the green door marker is for the floor, not for things on it
        program.setVector4("MELensMarkerSize", 0f, 0f, 0f, 0f);
        program.setVector3("MELensMarkerColour", 0f, 0f, 0f);
        program.setVector4("MELensShade", RV.shadeX, RV.shadeY, RV.shadeStrength, 2f);   // 2: furniture lighting, any texture size
        program.setValue("MELensSpotCount", 0f);
        program.setVector4("MELensWallTint", 0f, 0f, 0f, 0f);
        program.setVector4("MELensWellCut", RV.wellPlaneD, RV.wellFloorD, RV.wellFloorSet ? 1f : 0f, 0f);
        float[] clip0 = RV.clipBoxes[0];
        float[] clip1 = RV.clipBoxes[1];
        program.setVector3("MELensClipMin0", clip0[0], clip0[1], clip0[2]);
        program.setVector3("MELensClipMax0", clip0[3], clip0[4], clip0[5]);
        program.setVector3("MELensClipMin1", clip1[0], clip1[1], clip1[2]);
        program.setVector3("MELensClipMax1", clip1[3], clip1[4], clip1[5]);
    }

    private static void drawOne(Shader shader, ShaderProgram program, Matrix4f body, Entry entry) {
        if (entry.texture == null || !entry.texture.isReady() || entry.mesh == null || !entry.mesh.isReady()) {
            return;
        }
        placed.set(body).mul(entry.toBody);
        PZGLUtil.pushAndMultMatrix(5888, placed);
        try {
            GL13.glActiveTexture(33984);
            shader.setTexture(entry.texture, "Texture", 0);
            shader.setTint(entry.red, entry.green, entry.blue);
            program.setValue("MELensToBody", entry.toBody);
            program.setVector4("MELensUv", entry.uv[0], entry.uv[1], entry.uv[2], entry.uv[3]);
            if (entry.ghost) {
                if (entry.valid) {
                    program.setVector4("MELensGhost", RV.ghostRed, RV.ghostGreen, RV.ghostBlue, 1f);
                } else {
                    program.setVector4("MELensGhost", 0.95f, 0.30f, 0.28f, 1f);
                }
            } else {
                program.setVector4("MELensGhost", 0f, 0f, 0f, 0f);
            }
            entry.mesh.Draw(shader);
        } finally {
            PZGLUtil.popMatrix(5888);
        }
    }

    static String status() {
        return "entries=" + entries.length + " ghost=" + (ghost != null) + " drawn=" + drawn.get()
                + " drawMicros=" + String.format(java.util.Locale.ROOT, "%.0f", averageMicros)
                + " cache=" + cache.size() + " disabled=" + disabled + (lastError == null ? "" : " error=" + lastError);
    }

    static void retry() {
        disabled = false;
        lastError = null;
        reported = 0;
    }

    /** A new game (or a return to the menu): what was resolved against the old models is not used again. */
    static void reset() {
        clear();
        cache.clear();
        retry();
    }
}
