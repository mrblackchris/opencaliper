git status
git add .
git commit -m "Add LTspice AC RAW import support"

git tag -a OpenCaliperV1.17 -m "OpenCaliperV1.17"
git push --atomic origin main refs/tags/OpenCaliperV1.17