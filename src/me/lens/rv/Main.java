package me.lens.rv;

import me.zed_0xff.zombie_buddy.Exposer;

/** ZombieBuddy entry point. The patches in this package are discovered by ZombieBuddy itself. */
public final class Main {
    private Main() {}

    public static void main(String[] arguments) {
        Exposer.exposeClass(RV.class);
        // Load (not initialise) the classes the animal hooks patch before ZombieBuddy applies the patches (it runs this
        // first): IsoSprite was otherwise loaded while the patches were being applied, after ZombieBuddy listed the loaded
        // classes and before its hook for new ones, and stayed unpatched (no animals drawn).
        for (String name : new String[] { "zombie.iso.sprite.IsoSprite", "zombie.core.skinnedmodel.advancedanimation.AnimatedModel$WorldModelCamera",
                "zombie.inventory.ItemContainer", "zombie.inventory.types.Food", "zombie.iso.IsoGridSquare" }) {
            try {
                Class.forName(name, false, Main.class.getClassLoader());
            } catch (Throwable t) {
                System.out.println("[ME_LENS] could not load " + name + " before patching: " + t);
            }
        }
        System.out.println("[ME_LENS] walk-in RV " + RV.VERSION + " loaded (hooks: vehicle cutaway and interior light, cabin facing, standing animations)");
    }
}
