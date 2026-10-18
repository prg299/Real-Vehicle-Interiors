package me.lens.rv;

import me.zed_0xff.zombie_buddy.Exposer;

/** ZombieBuddy entry point. The patches in this package are discovered by ZombieBuddy itself. */
public final class Main {
    private Main() {}

    public static void main(String[] arguments) {
        Exposer.exposeClass(RV.class);
        System.out.println("[ME_LENS] walk-in RV " + RV.VERSION + " loaded (hooks: vehicle cutaway and interior light, cabin facing, standing animations)");
    }
}
