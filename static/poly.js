/* часть функций JS, те, что получилось вытащить, выынесены сюда */	

// создает полигон и возвращает его
function create_path(dx,dy,x,y){
	//console.log("pt=",pt);
	var pt; // тут нельзя этого писать так передается масссив всех полигонов, надо его передавать как параметр
	var stSize =50; // размеры вновь создаваемого полигона 
	if (dx<stSize&dy<stSize) pt = ["M", x0, y0, "L",x0+stSize,y0,"L",x0+stSize,y0+stSize,"L",x0,y0+stSize,"Z"].concat(pt);
	else if (dx<stSize) pt = ["M", x0, y0, "L",x0+stSize,y0,"L",x0+stSize,y,"L",x0,y,"Z"].concat(pt);
	else if (dy<stSize) pt = ["M", x0, y0, "L",x,y0,"L",x,y0+stSize,"L",x0,y0+stSize,"Z"].concat(pt);
	else pt = ["M", x0, y0, "L",x,y0,"L",x,y,"L",x0,y,"Z"].concat(pt);
	return pt;
};

// функция отсылает данные полигонов на сервер
function sendPolyToServer(req) {
	 var str_ = "req=" + encodeURIComponent(req);
	 $.ajax({
                type: "POST",
                url: "/sendPolyToServer",
                //data: $('form').serialize(),
                data: str_,
                success: function(response) {
                    var json = jQuery.parseJSON(response)
                    console.log(response);
                },
                error: function(error) {
                    console.log(error);
                }
            });
}

function sendSettingsToServer(req){
	// var str_ = "req=" + encodeURIComponent(req);
	// str_ =  JSON.stringify(req);
	// console.log('req fro ssts stigifieght', req);
	$.ajax({
		type: "POST",
		url: "/sendSettingsToServer",
		// data: $('form').serialize(),
		data: req,
		type: 'POST',
		// processData: false,
		// contentType: false,
		success: function(response) {
			// var json = jQuery.parseJSON(response)
			// console.log(response); // {"ip": "/0", "gateway": "", "hub": "0.0.0.0"}
		},
		error: function(error) {
			(error);
		}
	});
}

function getStatusFromServer(polygones) {
	$.ajax({
				url: "/showStatus",
				data:"",
                type: 'POST',
                success: function(response) {
                    var json = jQuery.parseJSON(response)
                    {
						document.getElementById("polyData").innerHTML = "address: "+response; // Выводим ответ сервера
						//document.getElementById("tsNumberTable_1_0").innerHTML = json[1][0]; // раскомментирование этого приводит к тому что перестает работать отображение рамок на картинке
						//document.getElementById("tsNumberTable_1_1").innerHTML = json[1][1]; // то-же что и выше. возможно затык выполнения на этой строчке из-за ошибки.
						// polyStatus = json[0];
						// // console.log('json[0]=',json[0]);
						// status='';
						// for(i=0;i<polyStatus.length;i++){
						// 	if( polyStatus[i] == '0' | polyStatus[i] == '1' ) status += polyStatus[i];
						// };
						// for (i=0;i<(polygones.length);i++){
						// 	if (status[i]==0)
						// 		polygones[i].attr({stroke:"red",fill:"red"});
						// 	else if (status[i]==1)
						// 		polygones[i].attr({stroke:"green",fill:"green"});
						// }
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
				url: "/showStatusHub",
				data:"",
                type: 'GET',
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

function convertPolyToString(polygones,W,H,modes_poly,ramkiArrows){ // формирует JSON структуру из рамок
	currState =0; //режим работы рамки 0-Проезд(П), 1-Остановка(О)
	var string='{\n"polygones":\n[\n';
	for (var i=0;i<polygones.length;i++){ // формируем координаты точек полигонов
		string += "[\n";
		for (var j=0;j<4;j++){
			string += "[";
			string+=polygones[i].attr("path")[j][1]; // координата X точки полигона
			string+=",";
			string+=polygones[i].attr("path")[j][2]; // координата Y точки полигона
			if (j<3) string += "],\n";
			else string += "]\n";
		}
		if (i<polygones.length-1) string += "],\n";
		else string += "]\n";
	}
	string += ']\n,"frame":\n['+W+","+H+"]";
	string += '\n,"ramkiModes":\n['; // тут добавляем в файл типы рамок
	//console.log("modes_poly from  convertPolyToString =",modes_poly,modes_poly.length);
	if (modes_poly.length!=0) {
        for (var i = 0; i < modes_poly.length; i++) {  //формируем режимы работы рамок
            //strToCompare = modes_poly[i].attr("text");
            //currState =0;
            if (modes_poly[i].attr("text") == '-П')
                currState = 0;
            else if (modes_poly[i].attr("text") == '-О')
                currState = 1;
            else {
                console.log("Inpossible frame setting attr(text) = ", modes_poly[i].attr("text"), ' state= ', currState);
                //currState = 1;
            }
            if (i < polygones.length - 1)
                string += currState + ',';
        }
    }
	string+=currState+']';
	string += '\n,"ramkiDirections":\n[';
	for (var i=0;i<ramkiArrows.length;i++){  //формируем структуру стрелок - номер полигона вместо r.set здесь обычный массив. т.к. перебираемый массив из r.set сделать не получилось... РАЗОБРАТЬСЯ ПОЧЕМУ...
		string += "\n[";
		for (var j=0;j<4;j++){
			if (ramkiArrows[i][j]==1)
				currState="1"
			else
				currState="0";
			if (j<3) string += currState+",";
			else string += currState+"]";
		}
		if (i<ramkiArrows.length-1) string += ",";
		else string += "\n";
	}
	string += ']\n}\n';
	//console.log("string from conv",string);
	return string
}

