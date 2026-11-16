git status
git add .
git commit -m "Add LTspice AC RAW import support"

git tag -a OpenCaliperV1.19 -m "OpenCaliperV1.19"
git push --atomic origin main refs/tags/OpenCaliperV1.19