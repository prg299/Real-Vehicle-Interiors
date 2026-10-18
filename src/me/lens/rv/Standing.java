package me.lens.rv;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.characters.action.ActionGroup;

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

    private Standing() {}

    static boolean isStanding(IsoPlayer player) {
        return player != null && standing.contains(player)
                && !player.getVariableBoolean("bEnteringVehicle")
                && !player.getVariableBoolean("bExitingVehicle");
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
