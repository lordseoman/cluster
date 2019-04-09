
for x in `docker ps -a | grep jet-processor | awk -F' ' '{print $1}'`; do echo $x; docker logs --tail 20 $x; done
for x in `docker ps | grep jet-processor | awk -F' ' '{print $1}'`; do echo $x; docker exec -it $x grep AUTH bin/exportGriffith.sh; done
for x in `docker ps | grep jet-processor | awk -F' ' '{print $1}'`; do echo $x; docker exec -it $x grep mysql bin/exportGriffith.sh; done


for x in `docker ps | grep jet-processor | awk -F' ' '{print $1}'`; do echo $x; docker exec -it $x /opt/patches/jet/updateBin.sh; done
./bin/update.sh
docker ps


sudo -E -u ec2-user /home/ec2-user/bin/update.sh
for x in `docker ps | grep jet-processor | awk -F' ' '{print $1}'`; do echo $x; docker exec -td $x /opt/patches/jet/updateBin.sh; done

docker exec -td --user jet $x bin/doGriffithExport.sh

