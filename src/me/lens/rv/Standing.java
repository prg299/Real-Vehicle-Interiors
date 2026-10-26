package me.lens.rv;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.characters.action.ActionGroup;
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
    private static final class MotionScratch {
        final Vector2 delta = new Vector2();
        final Vector3f origin = new Vector3f(), unit = new Vector3f();
    }
    private static final ThreadLocal<MotionScratch> motion = ThreadLocal.withInitial(MotionScratch::new);

    private Standing() {}

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
        if (!isStanding(player)) return 0f;
        MotionScratch scratch = motion.get();
        player.getDeferredMovement(scratch.delta);
        float distance = scratch.delta.getLength();
        if (!Float.isFinite(distance) || distance <= 0f) return 0f;
        var vehicle = player.getVehicle();
        vehicle.getLocalPos(player.getX(), player.getY(), 0f, scratch.origin);
        vehicle.getLocalPos(player.getX() + 1f, player.getY(), 0f, scratch.unit);
        double scale = Math.hypot(scratch.unit.x - scratch.origin.x, scratch.unit.z - scratch.origin.z);
        double localDistance = distance * scale;
        return Double.isFinite(localDistance) ? (float) localDistance : 0f;
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
