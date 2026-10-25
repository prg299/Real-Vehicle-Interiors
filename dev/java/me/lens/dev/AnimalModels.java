package me.lens.dev;

import java.lang.reflect.Field;
import java.util.Map;
import me.zed_0xff.zombie_buddy.Exposer;
import zombie.characters.animals.IsoAnimal;
import zombie.core.skinnedmodel.advancedanimation.AnimatedModel;
import zombie.vehicles.BaseVehicle;

/** Read-only observation of the actual interior models, never the animal's outside animator. */
@Exposer.LuaClass(name="MELensDevAnimalModels")
public final class AnimalModels {
    private static String quote(String text) {
        return "\"" + String.valueOf(text).replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    public static String snapshot() throws Exception {
        Field field=Class.forName("me.lens.rv.Animals").getDeclaredField("slots");
        field.setAccessible(true);
        Map<?,?> slots=(Map<?,?>)field.get(null);
        Field ownerField=Class.forName("me.lens.rv.Animals").getDeclaredField("owner");ownerField.setAccessible(true);
        Object owner=ownerField.get(null);
        StringBuilder out=new StringBuilder("[");
        for (var entry:slots.entrySet()) {
            Field mf=entry.getValue().getClass().getDeclaredField("model");mf.setAccessible(true);
            AnimatedModel model=(AnimatedModel)mf.get(entry.getValue());
            IsoAnimal animal=(IsoAnimal)entry.getKey();
            if(out.length()>1)out.append(',');
            out.append("{\"id\":").append(animal.getAnimalID())
                .append(",\"type\":").append(quote(animal.getAnimalType()))
                .append(",\"active\":").append(owner instanceof BaseVehicle vehicle
                    && vehicle.getAnimalById(animal.getAnimalID()) == animal)
                .append(",\"requestedSet\":").append(quote(animal.GetAnimSetName()))
                .append(",\"modelSet\":").append(quote(model.GetAnimSetName()))
                .append(",\"loadedSet\":").append(quote(model.getAdvancedAnimator().animSet==null ? null : model.getAdvancedAnimator().animSet.name))
                .append(",\"ready\":").append(model.isReadyToRender())
                .append(",\"animate\":").append(model.isAnimate())
                .append(",\"state\":").append(quote(model.getAdvancedAnimator().getCurrentStateName()))
                .append(",\"actionState\":").append(quote(model.getActionContext().getCurrentStateName()))
                .append(",\"tracks\":[");
            boolean first=true;
            for(var track:model.getAnimationPlayer().getMultiTrack().getTracks()) {
                if(!first)out.append(',');first=false;
                out.append("{\"name\":").append(quote(track.getName()))
                    .append(",\"time\":").append(track.getCurrentTimeValue())
                    .append(",\"duration\":").append(track.getDuration())
                    .append(",\"weight\":").append(track.getBlendWeight())
                    .append(",\"playing\":").append(track.isPlaying).append('}');
            }
            out.append("]}");
        }
        return out.append(']').toString();
    }
}
