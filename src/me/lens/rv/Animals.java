package me.lens.rv;

import java.util.ArrayList;
import java.util.Map;
import java.util.WeakHashMap;
import org.joml.Vector3f;
import zombie.characters.animals.IsoAnimal;
import zombie.core.SpriteRenderer;
import zombie.core.skinnedmodel.advancedanimation.AdvancedAnimator;
import zombie.core.skinnedmodel.advancedanimation.AnimatedModel;
import zombie.core.textures.TextureDraw;
import zombie.iso.Vector2;
import zombie.vehicles.BaseVehicle;

/**
 * Animals inside: an animal put down in a vehicle lives in the vehicle's own animal list, as in a livestock trailer,
 * where the game updates it but never draws it. Here each one is drawn as the game draws a mannequin: an
 * {@link AnimatedModel} with the animal's own look and anim set, queued with {@link SpriteRenderer#drawGeneric}
 * right after the vehicle you are in queues its own draw, at its place inside, in the vehicle's depth (the depth a
 * passenger inside gets, {@link Cutaway#cabinDepth}, set after the model's world camera chose the depth of the
 * animal's own square), so walls and furniture in front of it hide it. Lua publishes only for the vehicle you stand in
 * (MELens_AnimalsUI.lua).
 *
 * Lua (main thread) publishes the list ({@link #begin}, {@link #add}, {@link #end}): the animal, where it stands
 * (passenger space), which way it faces, the anim state and the idle action. The models are updated and queued on
 * the main thread when the vehicle renders; the render thread only draws what was queued.
 */
public final class Animals {
    static final class Entry {
        final IsoAnimal animal;
        final float x, z, facing;
        final String state, action;

        Entry(IsoAnimal animal, float x, float z, float facing, String state, String action) {
            this.animal = animal;
            this.x = x;
            this.z = z;
            this.facing = facing;
            this.state = state;
            this.action = action;
        }
    }

    /** One animal's model and its three drawers (one per sprite renderer state, as the mannequin keeps them). */
    private static final class Slot {
        final AnimatedModel model = new AnimatedModel();
        final Drawer[] drawers = new Drawer[3];
        IsoAnimal lookOf;
        long lookAt;

        Slot() {
            for (int i = 0; i < drawers.length; i++) {
                drawers[i] = new Drawer(model);
            }
        }
    }

    private static final class Drawer extends TextureDraw.GenericDrawer {
        private final AnimatedModel model;
        private float x, y, z, angle;
        private Object vehicle;
        private boolean rendered;

        Drawer(AnimatedModel model) {
            this.model = model;
        }

        void init(Object vehicle, float x, float y, float z) {
            this.vehicle = vehicle;
            this.x = x;
            this.y = y;
            this.z = z;
            this.rendered = false;
            model.renderMain();
            angle = model.getAnimationPlayer().getRenderedAngle();
        }

        @Override
        public void render() {
            if (disabled) {
                return;
            }
            try {
                drawing = this;
                model.DoRenderToWorld(x, y, z, angle);
                rendered = true;
                drawn.incrementAndGet();
            } catch (Throwable t) {
                fail("render", t);
            } finally {
                drawing = null;
            }
        }

        @Override
        public void postRender() {
            try {
                model.postRender(rendered);
            } catch (Throwable t) {
                fail("postRender", t);
            }
        }
    }

    private static final Entry[] NONE = new Entry[0];
    /** How often (ms) an animal's look is copied again (it grows, gets dirty, gets its saddlebags). */
    private static final long LOOK_EVERY = 5000L;

    /** The game's vertical unit: model units per floor level. */
    private static final float LEVEL = 2.44949f;
    /** How far below its level a character model's feet are drawn (model units: 1.5 x 0.48, Core.DoPushIsoStuff). */
    private static final float FEET = 0.72f;

    static volatile Entry[] entries = NONE;
    static volatile Object owner;
    static volatile float floorY;
    static volatile boolean disabled;
    /** Diagnostics: whether the cabin depth is used, where the last animal was drawn. */
    static volatile boolean depthOn = true;
    static volatile float lastX, lastY, lastZ;
    static volatile String lastState;
    static volatile String lastError;
    static final java.util.concurrent.atomic.AtomicLong drawn = new java.util.concurrent.atomic.AtomicLong();
    /** Diagnostics: vehicle renders seen, of the published vehicle, animals queued. */
    static volatile long calls, matched, queued;

    // main thread only
    private static final ArrayList<Entry> pending = new ArrayList<>();
    private static Object pendingOwner;
    private static float pendingFloorY;
    private static final Map<IsoAnimal, Slot> slots = new WeakHashMap<>();
    private static final Vector3f base = new Vector3f();
    private static final Vector3f at = new Vector3f();
    private static final Vector3f ahead = new Vector3f();
    private static final Vector2 direction = new Vector2();

    private Animals() {}

    // ------------------------------------------------------------------ Lua (main thread)

    public static void begin(BaseVehicle vehicle, double floor) {
        pending.clear();
        pendingOwner = vehicle;
        pendingFloorY = (float) floor;
    }

    public static void add(IsoAnimal animal, double x, double z, double facing, String state, String action) {
        if (animal != null) {
            pending.add(new Entry(animal, (float) x, (float) z, (float) facing, state, action));
        }
    }

    public static void end() {
        floorY = pendingFloorY;
        entries = pending.toArray(NONE);
        owner = pendingOwner;
        pending.clear();
    }

    public static void clear() {
        entries = NONE;
        owner = null;
    }

    public static String status() {
        return "animals=" + entries.length + " calls=" + calls + " matched=" + matched + " queued=" + queued + " drawn=" + drawn.get() + " disabled=" + disabled + (depthOn ? "" : " depth=off")
                + String.format(java.util.Locale.ROOT, " last=%.2f,%.2f,%.3f", lastX, lastY, lastZ) + " state=" + lastState
                + (lastError == null ? "" : " error=" + lastError);
    }

    public static void retry() {
        disabled = false;
        lastError = null;
    }

    // ------------------------------------------------------------------ IsoSprite.renderVehicle (main thread)

    /** After a vehicle queued its own draw: the animals inside the one you are in, queued right after it. */
    public static void afterVehicleRender(BaseVehicle vehicle) {
        calls++;
        if (vehicle != null && vehicle == owner) {
            matched++;
        }
        if (disabled || vehicle == null || vehicle != owner) {
            return;
        }
        Entry[] list = entries;
        if (list.length == 0) {
            return;
        }
        try {
            Vector3f offset = vehicle.getScript().getModel().getOffset();
            vehicle.getWorldPos(0.0f, 0.0f, 0.0f, base);
            float floor = floorY;
            int state = SpriteRenderer.instance.getMainStateIndex();
            long now = System.currentTimeMillis();
            for (Entry e : list) {
                Slot slot = slots.get(e.animal);
                if (slot == null) {
                    slot = new Slot();
                    slots.put(e.animal, slot);
                }
                AnimatedModel model = slot.model;
                // setCharacter builds the animator immediately. It must see the
                // animal's set, rather than AnimatedModel's mannequin default.
                String animationState = e.state == null ? "idle" : e.state;
                model.setAnimSetName(e.animal.GetAnimSetName());
                model.setState(animationState);
                if (slot.lookOf != e.animal || now - slot.lookAt > LOOK_EVERY) {
                    model.setCharacter(e.animal);
                    slot.lookOf = e.animal;
                    slot.lookAt = now;
                }
                // setState only names the state for the next rebuild of the model: the animator takes it here (it keeps
                // playing the state it has, so a walking animal otherwise slid in its idle pose)
                AdvancedAnimator animator = model.getAdvancedAnimator();
                if (!animationState.equals(animator.getCurrentStateName()) && animator.containsState(animationState)) {
                    animator.setState(animationState);
                }
                // the game's animals eat and drink with idleAction "eat"; Companion Dogs' dogs with cdEat and cdDrink
                String action = e.action == null ? "" : e.action;
                boolean moving = "walk".equals(animationState);
                boolean feeding = "eating".equals(animationState);
                // AnimatedModel updates its own ActionContext every frame.
                // Naming an animator state alone is immediately undone by the
                // native walk/eating -> idle transitions unless their variables
                // agree. These flags belong to this render model, not the live
                // trailer animal or Companion Dogs' outside AI.
                model.setVariable("bMoving", moving);
                model.setVariable("bPathfind", false);
                model.setVariable("isAnimalEating", feeding);
                model.setVariable("TrailerAnimation", "");
                model.setVariable("idleAction", "drink".equals(action) ? "eat" : action);
                model.setVariable("cdEat", "eat".equals(action));
                model.setVariable("cdDrink", "drink".equals(action));
                model.setVariable("cdRest", "sit".equals(action));
                model.setVariable("animalSpeed", moving ? 1.0f : 0.0f);
                model.setVariable("animalRunning", false);
                // where it stands: the vehicle's transform of its place (the vehicle may lean or drive)
                vehicle.getWorldPos(offset.x() + e.x, offset.y() + floor, offset.z() + e.z, at);
                float sin = (float) Math.sin(e.facing);
                float cos = (float) Math.cos(e.facing);
                vehicle.getWorldPos(offset.x() + e.x - sin, offset.y() + floor, offset.z() + e.z + cos, ahead);
                direction.set(ahead.x() - at.x(), ahead.y() - at.y());
                if (direction.getLength() > 1.0e-4f) {
                    direction.normalize();
                    model.setAngle(direction);
                }
                // The height as the game draws it: a vehicle's local height y lies at origin.y - 0.7 + y units
                // (ModelSlotRenderData's centerOfMassY), a character model's feet at level * 2.44949 - 0.72 units
                // (Core.DoPushIsoStuff); getWorldPos gives origin.y / 2.44949 + y.
                float level = base.z() + (at.z() - base.z() + FEET - BaseVehicle.centerOfMassMagic) / LEVEL;
                model.setAlpha(1.0f);
                model.update();
                Drawer drawer = slot.drawers[state];
                drawer.init(vehicle, at.x(), at.y(), level);
                lastState = animator.getCurrentStateName();
                lastX = at.x();
                lastY = at.y();
                lastZ = level;
                SpriteRenderer.instance.drawGeneric(drawer);
                queued++;
            }
        } catch (Throwable t) {
            fail("queue", t);
        }
    }

    // ------------------------------------------------------------------ the vehicle's depth this frame

    /** Render thread: the drawer whose model is being drawn now (its world camera begins inside). */
    private static Drawer drawing;

    /**
     * After the world camera of an animated model began: it gave the model the depth of the model's own square, which
     * lies tiles from the vehicle's in a long vehicle, so the vehicle hid the animal. Ours take the depth Real Vehicle
     * Interiors gives a passenger inside (the vehicle's own, a hair in front).
     */
    public static void afterCameraBegin() {
        Drawer d = drawing;
        if (d == null || !depthOn) {
            return;
        }
        float depth = cabinDepth(d.vehicle);
        if (!Float.isNaN(depth)) {
            d.model.setTargetDepth(depth);
        }
    }

    /** The depth a passenger inside that vehicle is drawn in this frame, or NaN (then the model's own depth stays). */
    static float cabinDepth(Object vehicle) {
        return Cutaway.cabinDepth(vehicle);
    }

    private static int reported;

    private static void fail(String where, Throwable t) {
        disabled = true;
        lastError = where + ": " + t;
        if (reported++ < 5) {
            System.out.println("[ME_LENS] animals inside: " + where + " failed, drawing them is off until retried: " + t);
            t.printStackTrace(System.out);
        }
    }
}
