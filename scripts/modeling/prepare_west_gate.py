"""Derive UV references from the two attributed photographs, not generated imagery."""
from pathlib import Path
import cv2, numpy as np, json
ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'static/ride/references/xipu-west-gate'
TEX=ROOT/'.tools/west-gate/textures'   # build inputs only; the GLB embeds what it needs
TEX.mkdir(parents=True,exist_ok=True)
a=cv2.imread(str(REF/'west-gate-01.jpg'))
scale=a.shape[1]/1824
corners=np.float32([[182,398],[1609,406],[1640,893],[149,897]])*scale
M=cv2.getPerspectiveTransform(corners,np.float32([[0,0],[3800,0],[3800,1250],[0,1250]]))
front=cv2.warpPerspective(a,M,(3800,1250))
cv2.imwrite(str(TEX/'facade-reference.jpg'),front,[cv2.IMWRITE_JPEG_QUALITY,95])
# Rectified, continuous top fascia, for subtle material texture sampling.
patch=front[15:70,180:1080]
patch=cv2.resize(patch,(1024,128))
# Mirroring gives continuous opposite borders without synthesizing architectural details.
tile=np.concatenate([patch,patch[:,::-1]],axis=1)
tile=np.concatenate([tile,tile[::-1]],axis=0)
cv2.imwrite(str(TEX/'terracotta.jpg'),tile,[cv2.IMWRITE_JPEG_QUALITY,95])
# Trace the photographed gold calligraphy to preserve the actual inscription contours.
hsv=cv2.cvtColor(front,cv2.COLOR_BGR2HSV)
mask=cv2.inRange(hsv,np.array([14,45,80]),np.array([42,230,255]))
mask[:100]=0;mask[245:]=0;mask[:,:1100]=0;mask[:,2680:]=0
mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((2,2),np.uint8))
contours,hierarchy=cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
paths=[]
for i,c in enumerate(contours):
 if cv2.contourArea(c)<6:continue
 c=cv2.approxPolyDP(c,.45,True).reshape(-1,2)
 paths.append({'points':[[round(float(x)/100-19,4),round(12.5-float(y)/100,4)] for x,y in c], 'hole':int(hierarchy[0][i][3])>=0})
(TEX/'inscription.json').write_text(json.dumps(paths))
cv2.imwrite(str(TEX/'inscription-mask.png'),mask)
# Front monument: preserve its original cut stone surface and engraved lettering.
b=cv2.imread(str(REF/'west-gate-02.jpg'));k=b.shape[1]/1824
pts=np.float32([[583,763],[1381,764],[1386,932],[579,923]])*k
m=cv2.getPerspectiveTransform(pts,np.float32([[0,0],[2048,0],[2048,450],[0,450]]))
stone=cv2.warpPerspective(b,m,(2048,450))
cv2.imwrite(str(TEX/'monument-reference.jpg'),stone,[cv2.IMWRITE_JPEG_QUALITY,95])
print('Saved photographic UV textures and',len(paths),'calligraphy contours.')
# Deterministic physical surface textures for the browser's standard PBR materials.
rng=np.random.default_rng(77)
for name,color,grain in [('asphalt',(73,77,77),12),('pavers',(139,140,132),7),('grass',(69,88,45),13)]:
 n=1024;fine=rng.normal(0,grain,(n,n));low=cv2.resize(rng.normal(0,grain,(32,32)),(n,n),interpolation=cv2.INTER_CUBIC)
 values=np.clip(np.array(color)[None,None,:]+(fine+low*.5)[:,:,None],0,255).astype(np.uint8)
 if name=='pavers':
  for y in range(0,n,128):
   values[y:y+3]=np.array([80,83,78])
   for x in range((y//128%2)*128,n,256):values[y:y+128,x:x+3]=np.array([80,83,78])
 cv2.imwrite(str(TEX/(name+'.jpg')),cv2.cvtColor(values,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,92])
 # Tangent-space normal derived from surface relief, never from scene silhouette.
 height=cv2.GaussianBlur(cv2.cvtColor(values,cv2.COLOR_RGB2GRAY).astype(np.float32)/255,(3,3),0)
 dx=cv2.Sobel(height,cv2.CV_32F,1,0);dy=cv2.Sobel(height,cv2.CV_32F,0,1)
 normal=np.dstack([-dx,-dy,np.ones_like(dx)]);normal/=np.linalg.norm(normal,axis=2,keepdims=True)
 cv2.imwrite(str(TEX/(name+'-normal.png')),cv2.cvtColor(cv2.resize(((normal*.5+.5)*255).astype(np.uint8),(512,512)),cv2.COLOR_RGB2BGR))
