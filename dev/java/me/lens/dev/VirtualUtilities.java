package me.lens.dev;

import me.zed_0xff.zombie_buddy.Exposer;
import zombie.vehicles.VirtualVehicle;

/** Real native proxy boundary for the utility hotfix; never shipped. */
@Exposer.LuaClass(name = "MELensDevVirtualUtilities")
public final class VirtualUtilities {
    private VirtualUtilities() {}
    public static VirtualVehicle emptyOwner() { return new VirtualVehicle(); }
}
