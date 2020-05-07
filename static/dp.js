
        window.onload = function () {
            console.log('загрузка dp.js...');

            var hubData = document.getElementById('hub_Data'); // статус связи с коммутатором
            // var polyData = document.getElementById('polyData'); //

            // статус детекора считывать с сервера и обновлять на странице.
             function circleStatusRequest(){
                ////// getStatusFromServer(polygones); не надо
                getStatusHubFromServer();
            };
            intID = 0;
            // intID = setInterval(circleStatusRequest, 400);
            // setInterval(circleStatusRequest, 400);
            // console.log(intID);

            function debugInfoShow(event) { // при надажии d показывает статус связи с коммутором
                // var intID =0;
                var kep = event.which;
                //if (event.keyCode == shift && capslock)console.log("shiftCapslock");
                //console.info("Нажата клавиша",kep,"d - дигностика связи");
                if (kep == 68) { // 68 - код клавиши d; 46 -код клавиши del
                    if (hubData.style.visibility == "hidden")
                        {
                            hubData.style.visibility = "visible";
                            //включает генерацию POST запросов о состоянии связи с HUB'ом
                            intID = setInterval(circleStatusRequest, 400);
                            console.log('setInterval', intID);

                        }
                    else {
                            hubData.style.visibility = "hidden";
                            //и выключает когда состояние хаба не мониторится на клиенте,
                            // чтобы не засорять сеть
                            console.log('crearInterval', intID);
                            clearInterval(intID);
                        }
                    // if (polyData.style.visibility == "hidden") polyData.style.visibility = "visible"; else polyData.style.visibility = "hidden";
                };
            };
            document.body.onkeydown = debugInfoShow;
        }
