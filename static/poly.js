/* часть функций JS, те, что получилось вытащить, выынесены сюда */	

// функция отсылает данные полигонов на сервер
function sendPolyToServer(req) {
	 var str = "req=" + encodeURIComponent(req);
	 $.ajax({
                type: "POST",
                url: "/sendPolyToServer",
                //data: $('form').serialize(),
                data: str,
                success: function(response) {
                    var json = jQuery.parseJSON(response)
                    console.log(response);
                },
                error: function(error) {
                    console.log(error);
                }
            });
};

function sendSettingsToServer(){
	$.ajax({
		type: "POST",
		url: "/sendSettingsToServer",
		data: $('form').serialize(),
		type: 'POST',
		success: function(response) {
			var json = jQuery.parseJSON(response)
			console.log("Success SendSettings");
			console.log(response);
			return false;
		},
		error: function(error) {
			console.log("Error SendSettings");
			console.log(error);
			return false;
		}
	});
};

function fieldMatchChecker(){
	validIpMaskRegEx = /^(?!0)(?!.*\.$)((1?\d?\d|25[0-5]|2[0-4]\d)(\.|\/)){4}(([0-9]|[1-2][\d]|3[0-2]))$/; // 192.168.0.255/24
    validIpRegEx = /^(?!0)(?!.*\.$)((1?\d?\d|25[0-5]|2[0-4]\d)(\.|$)){4}$/; // 192.168.0.255
	if ( !document.ip_form.ip.value.match(validIpMaskRegEx) ){
		console.log('ip.value bad');
		alert ('IP/Mask mismatch!');
		return false;
    };
	if ( !document.ip_form.gateway.value.match(validIpRegEx) ){
		console.log('ip.gate bad');
		alert ('Gate address mismatch!');
		return false;
    };
	if ( !document.ip_form.hub.value.match(validIpRegEx) ){
		console.log('ip.hub bad');
		alert ('Hub address mismatch!');
		return false;
    };
	return true;
};

function formDataHandler(){
	// handled by onClick form
	if (fieldMatchChecker()){
		sendSettingsToServer();
	};
};

function getStatusFromServer(polygones) {
	$.ajax({
                type: "POST",
				url: "/showStatus",
				data:"",
                type: 'POST',
                success: function(response) {
                    var json = jQuery.parseJSON(response)
                    {
						document.getElementById("polyData").innerHTML = "state: "+response; // Выводим ответ сервера
						//document.getElementById("tsNumberTable_1_0").innerHTML = json[1][0]; // раскомментирование этого приводит к тому что перестает работать отображение рамок на картинке
						//document.getElementById("tsNumberTable_1_1").innerHTML = json[1][1]; // то-же что и выше. возможно затык выполнения на этой строчке из-за ошибки.
						polyStatus = json[0];
						// console.log('json[0]=',json[0]);
						status='';
						for(i=0;i<polyStatus.length;i++){
							if( polyStatus[i] == '0' | polyStatus[i] == '1' ) status += polyStatus[i];
						};
						for (i=0;i<(polygones.length);i++){
							if (status[i]==0)
								polygones[i].attr({stroke:"red",fill:"red"});
							else if (status[i]==1)
								polygones[i].attr({stroke:"green",fill:"green"});
						}
					};

                    //console.log('respons=+=',json);
                },
                error: function(error) {
                    //console.log(error);
                }
            });
}
function getTsTableFromServer() {
	$.ajax({
                type: "POST",
				url: "/showTsTable",
				data:"",
                type: 'POST',
                success: function(response) {
                    // var json = jQuery.parseJSON(response)
                    {
						document.getElementById("tsNumberTable").innerHTML = response; // Выводим таблицу сформированную в python
					}

                    // console.log('respons=+=',json);
                },
                error: function(error) {
                    //console.log(error);
                }
            });
}
function getStatusHubFromServer() {
	$.ajax({
                type: "POST",
				url: "/showStatusHub",
				data:"",
                type: 'POST',
                success: function(response) {
                    var json = jQuery.parseJSON(response)
                    {
                    	// console.log(json);
						document.getElementById("hub_Data").innerHTML = "HUB: "+json; // Выводим ответ сервера
					};

                    //console.log('respons=+=',json);
                },
                error: function(error) {
                    //console.log(error);
                }
            });
}
