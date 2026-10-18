package me.lens.dev;

import java.util.Locale;
import me.zed_0xff.zombie_buddy.Exposer;
import org.lwjgl.util.vector.Matrix4f;
import zombie.characters.IsoGameCharacter;
import zombie.core.skinnedmodel.animation.AnimationPlayer;
import zombie.core.skinnedmodel.model.SkinningData;

/**
 * DEVELOPER TEST MOD ONLY. A character's bone positions in its model space (y up, before
 * the game's 1.5 model scale), for placing seat and bed poses on furniture.
 */
@Exposer.LuaClass(name = "MELensDevBones")
public final class Bones {
    private Bones() {}

    /** Developer-only track continuity receipt; AnimationPlayer is not exposed to Lua. */
    public static String tracks(IsoGameCharacter character) {
        AnimationPlayer player = character == null ? null : character.getAnimationPlayer();
        if (player == null || !player.isReady()) return "[]";
        var multi = player.getMultiTrack();
        StringBuilder out = new StringBuilder("[");
        for (int i = 0; i < multi.getTrackCount(); i++) {
            var track = multi.getTrackAt(i);
            if (i > 0) out.append(',');
            String name = String.valueOf(track.getName()).replace("\\", "\\\\").replace("\"", "\\\"");
            out.append(String.format(Locale.ROOT,
                    "{\"id\":%d,\"name\":\"%s\",\"time\":%.6f,\"fraction\":%.6f,\"blend\":%.6f,\"speed\":%.6f}",
                    System.identityHashCode(track), name, track.getCurrentTimeValue(),
                    track.getCurrentTimeFraction(), track.getBlendWeight(), track.getSpeedDelta()));
        }
        return out.append(']').toString();
    }

    /** One line per bone: "name x y z". */
    public static String dump(IsoGameCharacter character) {
        AnimationPlayer player = character == null ? null : character.getAnimationPlayer();
        if (player == null || !player.isReady()) {
            return "no animation player";
        }
        SkinningData skinning = player.getSkinningData();
        StringBuilder out = new StringBuilder();
        int count = player.getModelTransformsCount();
        for (int i = 0; i < count; i++) {
            Matrix4f m = player.getModelTransformAt(i);
            out.append(skinning.getBoneAt(i).name)
                    .append(String.format(Locale.ROOT, " %.4f %.4f %.4f%n", m.m03, m.m13, m.m23));
        }
        return out.toString();
    }
}
