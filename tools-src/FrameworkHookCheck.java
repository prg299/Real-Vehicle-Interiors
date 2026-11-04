import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.ArrayList;
import me.zed_0xff.zombie_buddy.annotations.Patch;
import me.zed_0xff.zombie_buddy.transformers.Pipeline;
import net.bytebuddy.description.method.MethodDescription;
import net.bytebuddy.dynamic.loading.ByteArrayClassLoader;
import net.bytebuddy.matcher.ElementMatcher;
import net.bytebuddy.matcher.ElementMatchers;
import net.bytebuddy.pool.TypePool;

/** Runs the installed ZB3 matcher against the actual 42.21 method descriptions.
 * No game, native input or render session is started by this check. */
public final class FrameworkHookCheck {
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        var jar = Pipeline.transformPatchJar(Path.of(args[0]), "me.lens.rv");
        var loader = new ByteArrayClassLoader.ChildFirst(FrameworkHookCheck.class.getClassLoader(),
                jar.classes(), ByteArrayClassLoader.PersistenceHandler.MANIFEST);
        Class<?> engine = Class.forName("me.zed_0xff.zombie_buddy.PatchEngine");
        Method build = engine.getDeclaredMethod("buildAdviceMethodMatcher",
                String.class, boolean.class, Class.class, Method.class);
        build.setAccessible(true);
        var misses = new ArrayList<String>();
        int checked = 0, zeroArgument = 0;
        var pool = TypePool.Default.ofSystemLoader();
        for (String name : jar.patches()) {
            Class<?> patchClass = Class.forName(name, false, loader);
            Patch patch = patchClass.getAnnotation(Patch.class);
            if (patch == null) throw new AssertionError("Framework did not convert " + name);
            var target = pool.describe(patch.className()).resolve();
            var methods = target.getDeclaredMethods().filter(ElementMatchers.named(patch.methodName()));
            ElementMatcher<MethodDescription> matcher = (ElementMatcher<MethodDescription>)
                    build.invoke(null, patch.methodName(), patch.strictMatch(), patchClass, null);
            int matches = 0;
            for (var method : methods) if (matcher.matches(method)) matches++;
            if (matches == 0) misses.add(name + " -> " + patch.className() + "." + patch.methodName());
            if (!patch.strictMatch()) {
                if (methods.size() != 1 || !methods.getOnly().getParameters().isEmpty())
                    throw new AssertionError("Non-strict hook could select another overload: " + name);
                zeroArgument++;
            }
            checked++;
        }
        for (String miss : misses) System.out.println("UNMATCHED " + miss);
        System.out.println("Framework hooks=" + checked + " zeroArgument=" + zeroArgument
                + " unmatched=" + misses.size() + " nativeInput=false renderAcceptance=false");
        boolean expectMisses = args.length > 1 && args[1].equals("--expect-misses");
        if (expectMisses ? misses.isEmpty() : !misses.isEmpty())
            throw new AssertionError(expectMisses ? "Baseline did not reproduce" : "Unmatched production hooks");
    }
}
