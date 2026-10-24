import java.lang.reflect.*;
import java.util.*;
public class WeatherGeometryCheck {
 public static void main(String[] args) throws Exception {
  Class<?> weather=Class.forName("me.lens.rv.Weather"),point=Class.forName("me.lens.rv.Weather$Point");
  var constructor=point.getDeclaredConstructor(float.class,float.class);constructor.setAccessible(true);
  Object polygon=Array.newInstance(point,6);
  float[][] coordinates={{0,-10},{10,0},{0,10},{-10,0},{0,-10},{0,0}};
  for(int i=0;i<coordinates.length;i++)Array.set(polygon,i,constructor.newInstance(coordinates[i][0],coordinates[i][1]));
  Method hull=weather.getDeclaredMethod("hull",polygon.getClass());hull.setAccessible(true);
  Object outline=hull.invoke(null,polygon);
  if(Array.getLength(outline)!=4)throw new AssertionError("Expected four extreme vertices");
  Field active=weather.getDeclaredField("activeHull");active.setAccessible(true);active.set(null,outline);
  for(String name:new String[]{"minX","minY","maxX","maxY"}) {
   Field bound=weather.getDeclaredField(name);bound.setAccessible(true);bound.setFloat(null,name.startsWith("min")?-10:10);
  }
  Method skip=weather.getMethod("skip",float.class,float.class,float.class,float.class);
  Random random=new Random(7291);int cases=0;
  for(int i=0;i<10000;i++) {
   float x=random.nextFloat()*40-20,y=random.nextFloat()*40-20,w=random.nextFloat()*15,h=random.nextFloat()*15;
   float closestX=x>0?x:Math.min(0,x+w),closestY=y>0?y:Math.min(0,y+h);
   boolean expected=Math.abs(closestX)+Math.abs(closestY)<=10;
   boolean actual=(boolean)skip.invoke(null,x,y,w,h);
   if(actual!=expected)throw new AssertionError("Exterior/interior classification "+x+","+y+","+w+","+h);
   cases++;
  }
  active.set(null,null);
  if((boolean)skip.invoke(null,0f,0f,1f,1f))throw new AssertionError("Unarmed weather must pass through");
  System.out.println("Weather geometry: "+cases+" analytic diamond/rectangle comparisons; duplicate/interior hull vertices and unarmed state passed");
 }
}
