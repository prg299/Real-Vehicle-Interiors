package me.lens.rv;

import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.characters.action.ActionGroup;
import zombie.core.skinnedmodel.animation.AnimationPlayer;
import zombie.core.physics.Transform;
import zombie.vehicles.BaseVehicle;
import zombie.iso.Vector2;
import org.joml.Vector3f;

/**
 * Standing inside a camper uses the game's normal standing animations.
 *
 * The standing position is a vehicle passenger, and the game gives every passenger the
 * vehicle versions of two things: the "player-vehicle" action group (the state machine)
 * and the "player-vehicle" animation set (the clips per state), whose aiming, eating,
 * reading or fighting animations are all seated. For a character standing in a camper
 * (and not entering or leaving it) both lookups return the normal "player" versions
 * instead. Entering, leaving and KI5's seats and beds keep the vehicle versions.
 */
public final class Standing {
    static final Set<IsoGameCharacter> standing = ConcurrentHashMap.newKeySet();
    private static final ThreadLocal<IsoPlayer> choosing = new ThreadLocal<>();
    private static final ThreadLocal<IsoPlayer> passengerUpdate = new ThreadLocal<>();
    private static final MethodHandle movementInput = movementInput();
    private static final class MotionScratch {
        final Vector2 delta = new Vector2();
        final Vector3f unit = new Vector3f(), travel = new Vector3f();
        final Transform transform = new Transform();
        final IsoPlayer.MoveVars input = new IsoPlayer.MoveVars();
    }
    private static final ThreadLocal<MotionScratch> motion = ThreadLocal.withInitial(MotionScratch::new);

    private Standing() {}

    private static MethodHandle movementInput() {
        try {
            return MethodHandles.privateLookupIn(IsoPlayer.class, MethodHandles.lookup()).findVirtual(
                    IsoPlayer.class, "updateMovementFromInput", MethodType.methodType(void.class, IsoPlayer.MoveVars.class));
        } catch (ReflectiveOperationException error) {
            throw new ExceptionInInitializerError(error);
        }
    }

    /** The normal player branch updates these before animation selection. The
     * native passenger branch returns early, so standing passengers need the same
     * input/rate update without applying world-floor movement or losing the seat. */
    public static void updateNativeInput(IsoPlayer player) {
        if (!isStanding(player) || !player.isLocalPlayer()) return;
        MotionScratch scratch = motion.get();
        player.updateMovementRates();
        player.setJustMoved(false);
        scratch.input.strafeX = scratch.input.strafeY = 0f;
        if (!player.isAsleep() && !player.isPerformingAnAction() && !player.getIgnoreMovement()
                && !zombie.core.Core.getInstance().isDoingTextEntry()) {
            try {
                movementInput.invokeExact(player, scratch.input);
            } catch (Throwable error) {
                throw new IllegalStateException("Native standing input update failed", error);
            }
        }
        player.setVariable("DeltaX", scratch.input.strafeX);
        player.setVariable("DeltaY", scratch.input.strafeY);
    }

    static boolean isStanding(IsoPlayer player) {
        return player != null && standing.contains(player)
                && player.getVehicle() != null
                && !player.getVariableBoolean("bEnteringVehicle")
                && !player.getVariableBoolean("bExitingVehicle");
    }

    /** Feed the same movement callback that vanilla's player action group uses.
     * Passenger placement stays vehicle-relative; animation states and blends are
     * selected by the game's player group rather than high-priority idle clips. */
    public static boolean movingFor(IsoPlayer player, boolean original) {
        if (!isStanding(player)) return original;
        String pose = player.getVariableString("MELensCabin");
        return "Walk".equals(pose) || "Run".equals(pose);
    }

    public static boolean runningFor(IsoGameCharacter character, boolean original) {
        if (!(character instanceof IsoPlayer player) || !isStanding(player)) return original;
        return "Run".equals(player.getVariableString("MELensCabin"));
    }

    /** The exact deferred animation displacement used by ordinary walking,
     * converted from world tiles to this vehicle's passenger-space units. */
    public static float movementDistance(IsoPlayer player) {
        return movement(player).length();
    }

    /** Keep the native stride's direction, including a turning clip's root motion. */
    public static Vector3f movement(IsoPlayer player) {
        MotionScratch scratch = motion.get();
        scratch.travel.zero();
        if (!isStanding(player)) return scratch.travel;
        player.getDeferredMovement(scratch.delta);
        if (!Float.isFinite(scratch.delta.x) || !Float.isFinite(scratch.delta.y)) return scratch.travel;
        localDirection(player, scratch.delta.x, scratch.delta.y, scratch);
        return scratch.travel;
    }

    private static void localDirection(IsoPlayer player, float worldX, float worldY, MotionScratch scratch) {
        direction(player.getVehicle(), worldX, worldY, scratch);
    }

    private static Vector3f direction(BaseVehicle vehicle, float worldX, float worldY, MotionScratch scratch) {
        // Transform a vector, not two distant world points. Avoid rounding away
        // small root steps or introducing facing jitter as the player moves.
        vehicle.getWorldTransform(scratch.transform);
        scratch.transform.origin.zero();
        scratch.transform.inverse();
        scratch.travel.set(worldX, 0f, worldY);
        scratch.transform.transform(scratch.travel);
        scratch.travel.y = 0f;
        return scratch.travel;
    }

    public static Vector3f direction(BaseVehicle vehicle, float worldX, float worldY) {
        return direction(vehicle, worldX, worldY, motion.get());
    }

    /** The game's animation player owns body rotation, twist and turn animations. */
    public static void targetFacing(IsoPlayer player, double radians, boolean immediate) {
        if (!isStanding(player) || !Double.isFinite(radians)) return;
        MotionScratch scratch = motion.get();
        var vehicle = player.getVehicle();
        vehicle.getWorldTransform(scratch.transform);
        scratch.transform.origin.zero();
        scratch.unit.set((float) -Math.sin(radians), 0f, (float) Math.cos(radians));
        scratch.transform.transform(scratch.unit);
        float x = scratch.unit.x, y = scratch.unit.z;
        if (x*x + y*y < 1e-8f) return;
        player.setForwardDirection(x, y);
        if (immediate && player.hasAnimationPlayer()) {
            player.getAnimationPlayer().setTargetAndCurrentDirection(x, y);
        }
    }

    public static float facing(IsoPlayer player) {
        if (!isStanding(player)) return 0f;
        MotionScratch scratch = motion.get();
        float angle = player.hasAnimationPlayer() ? player.getAnimationPlayer().getAngle()
                : player.getDirectionAngleRadians();
        localDirection(player, (float) Math.cos(angle), (float) Math.sin(angle), scratch);
        return (float) Math.atan2(-scratch.travel.x, scratch.travel.z);
    }

    public static void publishFacing(IsoGameCharacter character) {
        if (character instanceof IsoPlayer player && isStanding(player) && player.isLocalPlayer()) {
            RV.facing.put(player, facing(player));
        }
    }

    public static void beginPassengerUpdate(IsoPlayer player) {
        beginChoosing(player);
        if (isStanding(player)) passengerUpdate.set(player);
    }

    public static void endPassengerUpdate() {
        passengerUpdate.remove();
        endChoosing();
    }

    /** Suppress only the seated-passenger resets in updateWhileInVehicle. */
    public static boolean skipPassengerDirection(IsoGameCharacter character) {
        return passengerUpdate.get() == character && !character.isAiming();
    }

    public static boolean skipPassengerAngle(AnimationPlayer animation) {
        IsoPlayer player = passengerUpdate.get();
        return player != null && player.getAnimationPlayer() == animation;
    }

    public static void beginChoosing(IsoPlayer player) {
        if (isStanding(player)) {
            choosing.set(player);
        }
    }

    /** IsoPlayer.GetAnimSetName: "player" instead of "player-vehicle" while standing. */
    public static String animSetFor(IsoPlayer player, String name) {
        if ("player-vehicle".equals(name) && isStanding(player)) {
            return "player";
        }
        return name;
    }

    public static void endChoosing() {
        choosing.remove();
    }

    public static ActionGroup groupFor(String name, ActionGroup group) {
        if (choosing.get() != null && "player-vehicle".equals(name)) {
            return ActionGroup.getActionGroup("player");
        }
        return group;
    }
}
