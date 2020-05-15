
        // изменения от 14.03 устранена невозможность редактирования после сохранения.
        // изменения от 31.10 введены типы рамок - проезд и остановка. Данные типов хранятся в polygones.dat
        window.onload = function () {
            console.log('загрузка...');
            var W = document.getElementById('img_div').style.width.slice(0, -2), /*убирает "px" в конце*/
                H = document.getElementById('img_div').style.height.slice(0, -2),
                r = Raphael("holder", W, H);
            var req = "";// r.set; // массив  для хранения данных полигонов (похоже что это не r.set, а строка(см. вызовы convertPolyToString)
            var polygones = r.set(); 	//массив полигонов
            var rects = r.set(); 		// квадратики по углам полигонов
            var arrows = r.set();		// направления движения в рамках для настройки в web интерфейсе
			var setArrows =[]; 			// массив в котором лежат стрелки, где каждый член - стрелки отдельного полигона
			// var directionsSrv = r.set();// направления движения в рамке принятые с сервера и после радактирования отсылаемые на сервер. отказался...
            var rectsCover = r.set(); 	// массив четверок квадратиков по углам полигонов
            var nums = r.set(); 		// номера по которым работает функция построения
            var nums_poly = r.set(); 	// номера полигонов которые отображаются на странице
            var modes_poly = r.set();	// буквы, обозначающие режимы работы рамок(полигонов) 0(П) - присутствие, 1(О) - остановка
            var pt = [];  				// строка задания path полигона
            var k = 0; 					// номер полигона
            var polyFromServer = 6;		// структура, содержащая данные полигонов и режимы работы. 6 - дефолт для диагностики
            var polygonNumber;
            var ramkiModes; 			// вспомогательный массив, использующийся в назначении режимов работы рамок.
			var ramkiArrows;			// вспомогательный массив, исп. для хранения статуса стрелок с сервера.
            var editMode = 0;
            var zeroPolyAlert = document.getElementById('zeroPolyAlert'); // надпись о том что с сервера нет полигонов.
            var editModeAlert = document.getElementById('editModeAlert'); // индикатор режима Редактирования
            var hubData = document.getElementById('hub_Data'); // статус связи с коммутатором
            var polyData = document.getElementById('polyData'); //

            function getPolyFromServer(req) { // загружает данные полигонов из файла при открытии страницы в браузере
                var str = "req=" + encodeURIComponent(req);
                $.ajax({
                    type: "POST",
                    url: "/getPolyFromServer",
                    //data: $('form').serialize(),
                    data: str,
                    success: function(response) {
                        polyFromServer = jQuery.parseJSON(response)
                        //console.log('poly from GetPolygones=',response);
                        //polyFromServer = JSON.parse(polyFromServer);
                        // console.log('polyFromServer from getPolyFromServer=',polyFromServer);
                        console.log('polyFromServer from getPolyFromServer length=',polyFromServer.length);
                        //console.log('polyFromServer.indexOf(\"polygones\")=',polyFromServer.indexOf('polygones')); //3

                        if (polyFromServer.indexOf('polygones') >= 0) { // если файл с данными полигонов пустой, в нем не будет строки "polygones"
                            polyFromServer = JSON.parse(polyFromServer);
                            //console.log("polygones got from server: ",polyFromServer);
                            zeroPolyAlert.innerHTML = ""; // удаляем надпись о том, что данные полигонов не заданы
                            ramkiModes = polyFromServer.ramkiModes; //промежуточная переменная нужная для работы assygnPolygonMode
                            ramkiArrows = polyFromServer.ramkiDirections;
                            return polyFromServer;
                        }
                        else {
                            zeroPolyAlert.innerHTML = "Данные зон детектирования не заданы";
                            return 0;
                        }
                                //console.log("ramkiModes",ramkiModes);

                    },
                    error: function(error) {
                        console.log(error);
                        return 0;
                    }
                });
            };

            // назначает номера полигонов. при попытке переместить в файл не находит r,nums_poly,polygones
            function assygnPolygonNumber() {
                nums_poly.remove(); // при каждом вызове сначала удаляем все полигоны
                for (i = nums_poly.length - 1; i >= 0; i--)
                    nums_poly.splice(i, 1); // это тоже для удаления в дополнение к тому что выше, иначе не удаляется
                var attr = {font: "25px Helvetica", opacity: 0.7, fill: "yellow"};
                for (ii = 0; ii < polygones.length; ii++) {
                    text = ii + 1;
                    //console.log("polygones ii =", polygones[ii]);
                    x1 = polygones[ii].attr("path")[0][1]; //координаты точек полигона
                    y1 = polygones[ii].attr("path")[0][2];
                    x2 = polygones[ii].attr("path")[1][1];
                    y2 = polygones[ii].attr("path")[1][2];
                    x3 = polygones[ii].attr("path")[2][1];
                    y3 = polygones[ii].attr("path")[2][2];
                    x4 = polygones[ii].attr("path")[3][1];
                    y4 = polygones[ii].attr("path")[3][2];

                    x12 = (x1 + x2) / 2; // координаты проекций середины
                    x23 = (x2 + x3) / 2;
                    x34 = (x3 + x4) / 2;
                    x41 = (x4 + x1) / 2;
                    y12 = (y1 + y2) / 2;
                    y23 = (y2 + y3) / 2;
                    y34 = (y3 + y4) / 2;
                    y41 = (y4 + y1) / 2;

                    var np = nums_poly.push(r.text((x12 + x34) / 2 - 12, (y23 + y41) / 2, text).attr(attr));
                }
            }
            // отображает режим работы рамки 0(П) - присутствие, 1(О) - остановка
            function assygnPolygonMode() {
                var internFlag = 0;
                modes_poly.remove(); // при каждом вызове сначала удаляем все режимы рамок, иначе их призраки остаются на экране
                for (i = modes_poly.length - 1; i >= 0; i--)
                    modes_poly.splice(i, 1); // это тоже для удаления в дополнение к тому что выше, иначе не удаляется
                var attr = {font: "25px Helvetica", opacity: 0.7, fill: "yellow", number: "number"};
                // если на сервере ничего нет, задаем пустые рамки
                if (ramkiModes == undefined) {
                    text = '-П';
                    ramkiModes = new Array(polygones.length);
                    for (ii = 0; ii < polygones.length; ii++)
                        ramkiModes[ii] = 0;
                }
                for (ii = 0; ii < polygones.length; ii++) {
                    //эта штука просто подготавливает текст для картинки.
                    if (ramkiModes[ii] > 0)
                        text = '-О';
                    else
                        text = '-П';
                    {
                        x1 = polygones[ii].attr("path")[0][1]; //тут фиксируются в переменных координаты точек полигона
                        y1 = polygones[ii].attr("path")[0][2];
                        x2 = polygones[ii].attr("path")[1][1];
                        y2 = polygones[ii].attr("path")[1][2];
                        x3 = polygones[ii].attr("path")[2][1];
                        y3 = polygones[ii].attr("path")[2][2];
                        x4 = polygones[ii].attr("path")[3][1];
                        y4 = polygones[ii].attr("path")[3][2];

                        x12 = (x1 + x2) / 2; // координаты проекций середины
                        x23 = (x2 + x3) / 2;
                        x34 = (x3 + x4) / 2;
                        x41 = (x4 + x1) / 2;
                        y12 = (y1 + y2) / 2;
                        y23 = (y2 + y3) / 2;
                        y34 = (y3 + y4) / 2;
                        y41 = (y4 + y1) / 2;
                    }
                    var mp = modes_poly.push(r.text((x12 + x34) / 2 + 9, (y23 + y41) / 2, text).attr(attr))
                        .mousedown(function () {
                            modes_polyNumber = null;
                            for (l = 0; l < modes_poly.length; l++) { // определяем в какой элемент ткнули мышой соспоставляя координаты текущего с каждым, номер совпавшего запоминаем
                                if (modes_poly[l].attr("x") == this.attr("x") & modes_poly[l].attr("y") == this.attr("y"))
                                    modes_polyNumber = l;
                            }
                            if (editMode == 1) {
                                if (internFlag == 0 & this.attr("text") == '-П') {
                                    this.attr({"text": "-О"});//this.attr("text")=='О';
                                    ramkiModes[modes_polyNumber] = 1;
                                }
                                else if (internFlag == 0) {
                                    this.attr({"text": "-П"});
                                    ramkiModes[modes_polyNumber] = 0;
                                }
                                internFlag = 1;
                            }
                            else
                                notEditModeAlert();
                        })
                        .mouseup(function () {
                            req = convertPolyToString(polygones, W, H, modes_poly,ramkiArrows); // req - строка состояния, которая отображает все статусы полигонов
                            sendPolyToServer(req);
                            internFlag = 0; //эта затычка нужна потому, что .mousedown вызывается несколько раз при однократном нажатии(хз почему)
                        })
                        .mouseover(function () {
                            if (editMode == 1)
                                this.node.style.cursor = "pointer";
                        })
                }
                return 0;
            }
			// ф-ция расставляет стрелки всех полигонов на экране. анализируя задание - массив ramkiArrows.
            function assygnArrowsMode(){
				//console.log("assygnArrowsMode entrance!");
				if (ramkiArrows==undefined||ramkiArrows.length==0)
					putNullsToRamkiArrows();
				while (ramkiArrows.length<polygones.length) // если рамки не соотв. полигонам надставляем ( при добавлении нового)
					ramkiArrows.push([0,0,0,0]);
				while (ramkiArrows.length>polygones.length)	// сюда не заходит, т.к. лишнее в ramkiArrows удаляется в даблклике, при уалени полигона, сделано для безопасности.
					ramkiArrows.pop();
				for (var i=0;i<polygones.length;i++){ //для каждого полигона вызываем вспом ф-цию рисования стрелочек.
					//console.log('polygones[i].attr(path)',polygones[i].attr("path"));
					directionArrowsCreate(i,polygones[i].attr("path"));
				}
			}
            var mainRect = r.rect(0, 0, W - 0, H/*-100*/).attr({fill: "#fff", opacity: 0}); //
            var mainRect2 = r.rect(0, 0, W - 0, H/*-100*/).attr({fill: "none", opacity: 0.3}); // только для отображения границ
            //console.log("editMode = ",editMode);
            // сдвиг левого верхнего угла картинки, slice - для удаления "px" с конца - старый вариант
            // var leftCornerShiftX = document.getElementById('centr_block').style.left.slice(0, -2);
            // var leftCornerShiftY = document.getElementById('centr_block').style.top.slice(0, -2);
            // новый
            var leftCornerShiftX = Math.round(document.getElementById('img_div').getBoundingClientRect().left);
            var leftCornerShiftY = Math.round(document.getElementById('img_div').getBoundingClientRect().top);
            console.log("leftCornerShiftX - ", leftCornerShiftX , "leftCornerShiftY", leftCornerShiftY);
            //polyFromServer = getPolyFromServerPHP(req); // забирает данные полигонов с сервера
            polyFromServer = getPolyFromServer(req); // забирает данные полигонов с сервера
			function putNullsToRamkiArrows(){
				if (ramkiArrows==undefined){ //если с сервера ничего не считалось( ну мало-ли что) создаем массив набитый нулями
					ramkiArrows=[];
					for(var i=0;i<polygones.length;i++)
						ramkiArrows.push([0,0,0,0]);
				}
			}
			// делает path для стрелочек направлений из path рамок. формат аргумента такой: [["M", 186, 322],["L", 186, 322]....
            // результирующий массив с координатами точек стрелочек вида [[[x,y],[x,y],[x,y]],[..],[..],[..]]
            function dirsPath(path) {
               var arrowsPath=[[[],[],[]],[[],[],[]],[[],[],[]],[[],[],[]]];
//                console.log(path[0][1]);
                for (polyKernel=0;polyKernel<4;polyKernel++){ //перебираем по всем 4-м углам полигона начиная с левого верхнего, создавая 4 стрелки
                    x1=arrowsPath[polyKernel][0][0] = path[polyKernel][1];          // координата x 1 угла стрелки совпадает с x первого угла полигона
                    y1=arrowsPath[polyKernel][0][1] = path[polyKernel][2];          // то-же для y
                    if (polyKernel<3) {                                               // для третьего угла полигона второй угол рамки будет нулевой угол полигона
                        x2 = arrowsPath[polyKernel][1][0] = path[polyKernel + 1][1];    // координата x 2 угла стрелки совпадает с x второго угла полигона
                        y2 = arrowsPath[polyKernel][1][1] = path[polyKernel + 1][2];        // то-же для y
                    }
                    else {
                        x2 = arrowsPath[polyKernel][1][0] = path[0][1];
                        y2 = arrowsPath[polyKernel][1][1] = path[0][2];
                    }
                    // найдем стороны прямоугольного треугольника - половинки основания стрелки
                    var a = Math.sqrt((x2-x1)*(x2-x1)+(y1-y2)*(y1-y2))/2;//первый катет
                    var b=a/2;                                           //второй катет просто задается как половина первого
                    if (b>H/20) b = H/20;                                       // чтоб стрелка не сильно выпирала на больших полигонах
                    var с=Math.sqrt(a*a+b*b);                            //гипотенуза
                    alfa = Math.atan((y1-y2)/(x2-x1));               //угол поворота основания стрелки к горизонту в радианах
                    shiftX = (Math.cos(alfa+Math.asin(b/с)))*с;                     // вспомогательные величины смещения по X
                    shiftY = (Math.sin(alfa+Math.asin(b/с)))*с;                     // вспомогательные величины смещения по Y
                    if (polyKernel!=2){
                        x3 = arrowsPath[polyKernel][2][0] = shiftX+x1;                  // координата x 3 угла стрелки
                        y3 = arrowsPath[polyKernel][2][1] = -shiftY+y1;
                    }
                    else {
                        x3 = arrowsPath[polyKernel][2][0] = -shiftX + x1;
                        y3 = arrowsPath[polyKernel][2][1] = shiftY + y1;
                    }// координата y 3 угла стрелки
                    if (polyKernel==3|polyKernel==1){
                        if (x1>x2){
                            x3 = arrowsPath[polyKernel][2][0] = -shiftX+x1;
                            y3 = arrowsPath[polyKernel][2][1] = shiftY+y1;
                        }
                    }
                }
                //console.log("arrowsPath = ",arrowsPath);
                return (arrowsPath);
            }
             // cтроит стрелочки направления движения в рамке для 1 полигона.
            function directionArrowsCreate(polygonNumber, path) {
				var strokeWidth;
				var opacity = 0.7;
				if (setArrows==null|setArrows==undefined)
					setArrows = new Array(polygones.length);
				//console.log("ramkiArrows=",ramkiArrows);
				//console.log("polygones.length=",polygones.length);
				if (ramkiArrows==undefined||ramkiArrows.length==0) //если с сервера ничего не считалось( ну мало-ли что) создаем массив набитый нулями
					putNullsToRamkiArrows();
				arrPath = dirsPath(path); // из path полигончиков делает стрелочки направления движения в рамке.
				for (polyKernel=0;polyKernel<4;polyKernel++){
					//console.log("polygones.length=",polygones.length);
					//console.log("ramkiArrows=",ramkiArrows);
					if(ramkiArrows[polygonNumber][polyKernel]==0){
						strokeWidth=0;
						//opacity = 0.3;
					}
					else{
						strokeWidth=3;
						opacity = 0.7;
					}
					setArrows[polygonNumber] = arrows.push(r.path(
					    "M" + arrPath[polyKernel][0][0] +" "+(arrPath[polyKernel][0][1])+
						"L" +(arrPath[polyKernel][1][0])+" "+(arrPath[polyKernel][1][1])+
						"L" +(arrPath[polyKernel][2][0])+" "+(arrPath[polyKernel][2][1])+
						"Z")
						.attr({	stroke: "red",fill: "transparent",
								"stroke-width":strokeWidth,
								opacity: opacity
							 }) // транспарент почему-то не хочет меняться ни на что другое.
						.data("arrowNumber",polyKernel)
						.data("polygonNumber",polygonNumber) //тут важно: data относится к r.path, см. на круглые скобки
						//.attr({stroke: "red",fill:"white",opacity: 0.3}))
						.mouseover(function(){
						    // console.log("over!");
							if (editMode == 1) {
                                // console.log("over! edit m=",editMode);
							    this.attr({fill:"red","stroke-width":"3","opacity":"0.7"});
								if (ramkiArrows[polygonNumber][this.data("arrowNumber")]==1)
									this.attr({"stroke-width":"3"});
								else{
								    // this.attr({"stroke-width":"0"});
								    // console.log("over!");
								};
							}
						})
						.mouseout(function(){
						    // console.log("out!");
							if (editMode == 1) {
								// this.attr({"stroke":"red","stroke-width":"0","opacity":"0.3",fill:"red"})
								if (ramkiArrows[polygonNumber][this.data("arrowNumber")]==1)
									this.attr({"stroke-width":"3","opacity":"0.6"})
                                else {
                                    //this.attr({"stroke": "transparent","opacity":"1","fill":"red"})
                                    this.attr({"stroke-width":"0","fill":"transparent"})
                                    // console.log("out-else!!");
                                    // console.log('this.attr({"stroke"=', this.attr("stroke"));
                                    // console.log('this.attr({"stroke-width"=', this.attr("stroke-width"));
                                    // console.log('this.attr({"fill=', this.attr("fill"));
                                }
							}
						})
						.mousedown(function(){
						    // console.log("down!");
							if (editMode == 1) {
								this.attr({fill:"red","stroke-width":"3","opacity":"0.6"})
								//тут при клике в массив состояний стрелок ramkiArrows должна добавляться стрелка, если ее там еще нет, или удаляться, если она там есть.
								if (ramkiArrows[polygonNumber][this.data("arrowNumber")]==0)
									ramkiArrows[polygonNumber][this.data("arrowNumber")]=1
								else
									ramkiArrows[polygonNumber][this.data("arrowNumber")]=0
								//console.log("click!",this.data("arrowNumber"),this.data("polygonNumberA"));
								//console.log("click! - ramkiArrows",ramkiArrows);
							}
						})
						.mouseup(function(){
						    // console.log("UP!");
							if (editMode == 1) {
								if (ramkiArrows[polygonNumber][this.data("arrowNumber")]==1)
									this.attr({"stroke-width":"3","opacity":"0.6"})
								else {
                                    this.attr({"stroke-width": "0","opacity":"0"});
                                    // console.log("UP_ELSE!");
                                };

								//assygnArrowsMode();
								req = convertPolyToString(polygones, W, H, modes_poly,ramkiArrows); // modes_poly здесь это r.set
								sendPolyToServer(req);
								//};
								//setTimeout(supp,3000);
							}
						})
                        // .mousemove(function() {
                        //     if (editMode == 1) {
                        //         if (ramkiArrows[polygonNumber][this.data("arrowNumber")]==1)
							// 		this.attr({"stroke-width":"3","opacity":"0.6"})
							// 	else
							// 		this.attr({"stroke-width":"0"})
                        //     }
                        // })
                    )
				}
				//console.log("setArrows=",setArrows)
            };
            ff = function (k, i) {
                polygones.push(
                    r.path(path).attr({stroke: "red", fill: "red", opacity: 0.5})
						.data("polygonNumber",i)
                        .mousedown(function () {
                            if (editMode == 1) {
                                //console.log("from интерн mdown: polygonNumber",polygonNumber);
                                leftCornerShiftX = Math.round(document.getElementById('img_div').getBoundingClientRect().left);
                                leftCornerShiftY = Math.round(document.getElementById('img_div').getBoundingClientRect().top);
                                begin_path = this.attr("path");
                                minx = Math.min.apply(null, [begin_path[0][1], begin_path[1][1], begin_path[2][1], begin_path[3][1]]); //минимальное число x в полигоне // это надо чтобы полигон за границы не выезжал
                                maxx = Math.max.apply((null), [begin_path[0][1], begin_path[1][1], begin_path[2][1], begin_path[3][1]]); //максимальное число x в полигоне
                                miny = Math.min.apply(null, [begin_path[0][2], begin_path[1][2], begin_path[2][2], begin_path[3][2]]); //минимальное число y в полигоне
                                maxy = Math.max.apply(null, [begin_path[0][2], begin_path[1][2], begin_path[2][2], begin_path[3][2]]); //максимальное число y в полигоне
                                // console.log('minx',minx, 'miny',miny, 'maxx',maxx,  'maxy',maxy);
                                if (rects != null) rects.remove();
                                if (arrows != null) arrows.remove();
                                // выясняем на каком полигоне приземлились мышкой
                                //for (i = 0; i < polygones.length; i++) {
                                //    if (polygones[i].attr("path")[0][1] == this.attr("path")[0][1] & polygones[i].attr("path")[0][2] == //this.attr("path")[0][2])
                                //        polygonNumber = i;
                                //    //console.log("from mdown: polygonNumber",polygonNumber);
                                //}
                            }
                            else
                                notEditModeAlert();
                        })
                        .mouseup(function () {
                            if (editMode == 1) {
                                //console.log(".ommouseup внутри ->  nums_poly = ",nums_poly);
                                if (nums_poly != null) nums_poly.remove();
                                if (rects != null) rects.remove(); // удаляем квадратики по углам, если они там остались от каких-то предыдущих действий
                                if (arrows != null) arrows.remove(); // так же удаляем срелки направлений
                                path_ = this.attr("path");
                                // если начать строить полигон у нижнего или правого края окна, может случиться, что полигон нарисуется вне окна.
                                // надо его тогда приподнять и/или отдвинуть влево
                                //console.log('path_[i][1]',path_[0][1],path_[1][1],path_[2][1],path_[3][1]);
                                //console.log('path_[i][2]',path_[0][2],path_[1][2],path_[2][2],path_[3][2]);
                                if (path_[1][1] > W) { // если вторая точна выползла то подвинуть влево все
                                    jumpx = path_[1][1] - W;
                                    for (i = 0; i < 4; i++) path_[i][1] -= jumpx;
                                    //this.attr({path:path_});
                                }
                                if (path_[2][2] > H) { // если 3 точка выползла, то приподнять все
                                    jumpy = path_[2][2] - H;
                                    for (i = 0; i < 4; i++) path_[i][2] -= jumpy;
                                    //this.attr({path:path_});
                                }
                                this.attr({path: path_});
                                //if (maxy>H) for (i=0;i,4;i++) path_[i][2]-=maxy-H;
                                // для всех 4-х углов полигона рисуем квадратики за которые будем таскать
                                for (ii = rects.length - 1; ii >= 0; ii--) rects.pop();//splice(i,1); //удалем старые квадратики перед созд. новых
                                for (ii = arrows.length - 1; ii >= 0; ii--) arrows.pop(); //удалем старые стрелки направлений перед созд. новых
                                for (ii = 0; ii < 4; ii++) {
                                    var internalFlag=0;
                                    // создать квадратики по углам полигона
                                    var rec = rects.push(r.rect(path_[ii][1] - 10, path_[ii][2] - 10, 20, 20).attr({stroke: "red",fill: "yellow",opacity: 0.5}))
                                        .drag(function (dx, dy, x, y) { // таскать за квадратики по углам
                                            leftCornerShiftX = Math.round(document.getElementById('img_div').getBoundingClientRect().left);
                                            leftCornerShiftY = Math.round(document.getElementById('img_div').getBoundingClientRect().top);
                                            //internalFlag=1;
                                            if (arrows != null) arrows.remove(); // удаляем срелки направлений
                                            x = x - leftCornerShiftX;
                                            y = y - leftCornerShiftY;
                                            //this.attr({height:20,width:20,x:x-10,y:y-10});
                                            this.attr({height: 20, width: 20});
                                            var new_path = polygones[k - 1].attr("path");
                                            var numOfRect;
                                            for (j = 0; j < rects.length; j++) {
                                                if (rects[j].attr("x") == this.attr("x") & rects[j].attr("y") == this.attr("y")) numOfRect = j;
                                                //console.log("numOfRect=",numOfRect);
                                            }
                                            //console.log("this.attr(x,y) = ",this.attr("x"),this.attr("y"));
                                            //console.log("numOfRect =  ",numOfRect);
                                            if (x > 0 && x < W) {
                                                new_path[numOfRect][1] = x;
                                                this.attr({x: x - 10});
                                            }
                                            if (y > 0 && y < H) {
                                                new_path[numOfRect][2] = y;
                                                this.attr({y: y - 10});
                                            }
                                            polygones[k - 1].attr({path: new_path});
                                            assygnPolygonNumber();
                                            assygnPolygonMode();
                                            assygnArrowsMode();
                                            req = convertPolyToString(polygones, W, H, modes_poly,ramkiArrows); // *********************** //
                                        })
								}
								// теперь рисуем стрелки направлений
								//directionArrowsCreate(this.data("polygonNumber"),path_); // в функцию создания стрелок передается номер и path полигона.
								//console.log("this.data(polygonNumber)=",this.data("polygonNumber"));
                                rectsCover.push(rec); // и потом их суем в общий для них всех сет
                                text = k;//this.start.k;
                                // расставляем номера полигонов
                                assygnPolygonNumber();
                                assygnPolygonMode();
								assygnArrowsMode();
								//console.log("setArrows=",setArrows);
								req = convertPolyToString(polygones, W, H, modes_poly,ramkiArrows); // modes_poly здесь это r.set
                                sendPolyToServer(req);
                            }
                            else
                                notEditModeAlert();
							//console.log("polygones.length=",polygones.length);
                        })
                        .dblclick(function () {  // по двойному клику удаляется полигон
                            if (editMode == 1) {
								pnumber= this.data("polygonNumber"); // номер полигона, который мочим, пригодится.
								if (nums_poly != null) nums_poly.remove();
                                polygones.splice(this.start.k - 1, 1); //polygones.pop(1); // удаляет элемент из массива полигонов
                                this.remove(); // удаляет прямоугольник
                                if (rects != null) rects.remove();
                                if (arrows != null) arrows.remove();
                                //console.log("this.start из doubleclick end= ",k);
                                //console.log("polygones from dblcklick до del: !! ", polygones); // ок, полигоны не содержат одного удаленного
                                /*/ попробовать быстрый путь: сбросить полигоны после удаления на сервак и перезагрузить страницу.
                                // это работает ограниченно: после перезагрузки не устанавливается назад режим редактирования и и текст кнопки сохранить.
                                   setTimeout в этом случае не выход, см ниже , т.к. в него управление тупо не заходит, оно теряется после перезагрузки.
                                   req=convertPolyToString(polygones,W,H,modes_poly,ramkiArrows);
                                   sendPolyToServer(req);
                                // перезагрузить страницу
                                   document.location.reload();	//перезагрузка страницы
                                   setTimeout(function(){
                                      editMode = 1;	// включить р.р. , бо он выключается после перезагрузки ,
                                      editButton.value ='Сохранить'; // и кнопку вернуть как была
                                   },500);
                                //*/
                                // другой путь: без перезагрузки страницы. path всех полигонов (без удаленного) сохраняем в переменной, потом все удаляем и по новой вызываем ff()
                                //temp_polygones=polygones; // так нельзя. объекты js всегда передаются по ссылке
                                //temp_polygones=polygones.clone(); // рафаэлевский метод клонирования объектов не годится - после него появляются прямоугольники откуда не ждали
                                // не буду делать клон всего объекта, сделаю только список path полигонов потом полигоны удалю
                                pathList = []; // сюда перед удалением сгрузим все path всех полигонов
                                for (i = 0; i < polygones.length; i++) {
                                    pathList[i] = polygones.items[i].attr("path"); //массив углов полигона
                                }
                                delete_all();
                                //console.log("polygones from dblcklick после del:  !! ", polygones); // ок, полигоны пустые!
                                //console.log("path from dblcklick после del:  !! ", pathList);
                                for (i = 0; i < pathList.length; i++) {
                                    k = i + 1;
                                    path = pathList[i]; //массив углов полигона
                                    ff(k, i);
                                    //console.log("k=====",k,i)
                                }
                                assygnPolygonNumber();
                                assygnPolygonMode();
								// перед assygnArrowsMode надо удалить кусок ramkiArrows именно этого полигона иначе рамки кочуют к другим полигонам.
								// а также удалить и
								ramkiArrows.splice(pnumber,1);
								setArrows.splice(pnumber,1);
								assygnArrowsMode();
                                req = convertPolyToString(polygones, W, H, modes_poly,ramkiArrows); // ************************************** //
								sendPolyToServer(req);
                                winOnmouseUp(); // при даблклике не происходит события поднятия мыши над окном. не знаю почему, поэтому вызываем функцию, которую выполняет это событие, когда оно происходит.
                                //console.log("k после win mouse Up",k);
                                //*/
                            }
                            else
                                notEditModeAlert();
                        })
                        .drag(function (dx, dy, x, y) {
                                if (editMode == 1) {
                                    if (rects != null) rects.remove();
                                    if (arrows != null) arrows.remove();
                                    path_ = this.attr("path");
                                    for (i = 0; i < 4; i++) {
                                        if (minx + dx > 0 && maxx + dx < W) path_[i][1] = begin_path[i][1] + dx; // если углы полигона не выходят за края окна, двигаем его по x
                                        if (miny + dy > 0 && maxy + dy < H) path_[i][2] = begin_path[i][2] + dy; // и по y
                                    }
                                    ;
                                    this.attr({path: path_});
                                    assygnPolygonMode();
                                    assygnPolygonNumber();
                                    req = convertPolyToString(polygones, W, H, modes_poly,ramkiArrows); // ************************************** //
                                }
                                else
                                    notEditModeAlert();
                            }, function (x, y) {
                                //console.log("from func under drug: k=",k);
                                this.start = {k: k};
                            }
                        )//*/
                )
            }

            // рисует полигоны
            function circleff() {
                //console.log('polyFromServer = ',polyFromServer)
                //console.log('polygones = ',polyFromServer.polygones)
                if (polyFromServer !== undefined) {
                    for (i = 0; i < polyFromServer.polygones.length; i++) {
                        //console.log("k==",k,i)
                        k = i + 1;
                        corners = polyFromServer.polygones[i]; //массив углов полигона
                        path = ["M", corners[0][0], corners[0][1], "L", corners[1][0], corners[1][1], "L", corners[2][0], corners[2][1], "L", corners[3][0], corners[3][1], "Z"];
                        //console.log("path из цикла =",path);
                        ff(k, i);
                        //k++;
                        //console.log("k=====",k,i)
                    }
                }
                else {
                    //alert("данные зон детектирования не заданы");
                    console.log("The data didn't send. Try to increase timeout..")
                    path = [];
                }
            }
            var serverAnswerDelTime = 800;
            setTimeout(circleff, serverAnswerDelTime);
            setTimeout(assygnPolygonNumber, serverAnswerDelTime + 10);
            setTimeout(assygnPolygonMode, serverAnswerDelTime + 15);
			setTimeout(assygnArrowsMode, serverAnswerDelTime +20);

            //console.log("!!!!editMode = ",editMode);
            // обеспечивает функционал для случая добавления новых полигонов в режиме редактирования
            mainRect
                .mousedown(function (i, x, y, cx, cy) {
                    leftCornerShiftX = Math.round(document.getElementById('img_div').getBoundingClientRect().left);
                    leftCornerShiftY = Math.round(document.getElementById('img_div').getBoundingClientRect().top);
                    if (editMode == 1) {
                        //console.log("даун на поле","leftCornerShiftX,Y = ",leftCornerShiftX," , ",leftCornerShiftY);
                        x0 = x - leftCornerShiftX;
                        y0 = y - leftCornerShiftY;
                        path = [];
                        path = create_path(10, 10, x, y);
                        //pt=create_path(10,10,100,100);
                        //polygones.push(r.path(pt).attr({stroke:"red",fill:"red",opacity:0.5}));
                        k = polygones.length;
                        //console.log("!! k=",k);
						k++;
                        ff(k, k-1); //убавил на 1 второй аргумент.
						assygnArrowsMode(); // если тут не поставить всю конструкцию клинит
                    }
                    else {
                        notEditModeAlert();
                        zeroPolyAlert.innerHTML = "";
                    }
                })
                .drag(function (dx, dy, x, y) { // создает новый полигон
                    leftCornerShiftX = Math.round(document.getElementById('img_div').getBoundingClientRect().left);
                    leftCornerShiftY = Math.round(document.getElementById('img_div').getBoundingClientRect().top);
                    if (editMode == 1) {
                        //console.log('x0 x',x0,x);
                        //console.log("from new drug: k=",k,"polygones length = ",polygones.length);
                        if (rects != null) rects.remove();
                        if (arrows != null) arrows.remove();
                        x = x - leftCornerShiftX + 1; //+1 нужен для того, чтобы курсор был всегда над полигоном и функция mouseup срабатывала уверенно.
                        y = y - leftCornerShiftY + 1;
                        //console.log('x y',x,y);
                        if (x > W - 1) x = W - 1; // не дает вылазить за границы полигона
                        if (y > H - 1) y = H - 1;
                        pt = create_path(dx, dy, x, y);
                        //console.log("py =",pt,"polygones----",polygones);
                        if (polygones.items !== undefined) {
                            polygones.items[polygones.items.length - 1].attr({path: pt, opacity: 0.5});
                        }
                        else {
                            polygones.items[0].attr({path: pt, opacity: 0.5});
                        }
                        assygnPolygonNumber();
                        assygnPolygonMode();
						assygnArrowsMode();
                        //if (rects!= null)rects.remove();
                    }
                })
                /*
                .mouseover(function(){ // надо убирать стрелочки, если они не отмечены. mouseout на самой стрелочке не работает.
                    if(editMode==1){
                        for (plNum=0; plNum < ramkiArrows.length; plNum++){
                            for (plKernel=0;plKernel<4;plKernel++){
                                if (1){//(setArrows[plNum][plKernel].data("arrowNumber")==0) {
                                    //console.log("[plNum] ",plNum,"[plKernel]",plKernel,setArrows[plNum][plKernel].attr("stroke-width"));
                                    //setArrows[plNum][plKernel].attr({"stroke-width": "0"});
                                    //console.log('plNum, plKernel',plNum,plKernel, "attr=",setArrows[plNum][plKernel].attr("stroke-width"));//тут какаято херня!!!
                                }
                            }
                        };
                    }
                })
                //*/
            //.mouseup(function(){console.log(".ommouseup снаружи ->  nums_poly = ",nums_poly);}) // бесполезно что-то делать в этой ф-ции; она не отлавливается
            //.mousemove(function(x,y){console.log("k=!=!=",k);});
            var delButton = document.getElementById('delButton');
							
            //delButton.onclick = function delete_all(){
            function delete_all() {
                //var ret = confirm('Стереть?');
                if (editMode != 0) {
                    //*
					if (arrows != null) arrows.remove();
                    // след 2 строки удаляют полигоны и массив полигонов. порядок строк не менять, иначе полигоны не удаляются
                    polygones.remove();		// оставить строку, иначе остаются полигоны
                    for (i = polygones.length - 1; i >= 0; i--) polygones.splice(i, 1);	// оставить строку, иначе остаются нулевые члены массива
                    //console.log("polygones = ",polygones);
                    rects.remove();
                    rectsCover.remove();
                    nums.remove();
                    nums_poly.remove();
                    modes_poly.remove();
                    //*/
                    //r.clear(); // с этой байдой почему-то не начинает рисовать новые рамки сразу после нажатия "удалить все".
                    sendPolyToServer(req);
                    k = 0;//k=1;
                }
                else notEditModeAlert();
            }
            delButton.onclick = function () {
                delete_all();
            }; // без кавычек в такой записи нельзя: будет ошибка unexpected identifier
            //*
            var editButton = document.getElementById('editButton');
            editButton.onclick = function () {
                if (editMode == 0) { 	// если не в режиме редактирования,
                    editMode = 1;	// то включить р.р.
                    editButton.value = 'Сохранить';
                    editButton.innerHTML = 'Сохранить';
					delButton.disabled = ''; //false
                    //console.log ('delButton.disabled',delButton.disabled);
                    editModeAlert.innerHTML = "Режим редактирования";
                    editModeAlert.style.color = '#0000FF'
                }
                else { 				// если в нем,
                    editMode = 0;	// то выключить
                    editButton.value = 'Редактировать';
                    editButton.innerHTML = 'Редактировать';
					delButton.disabled = 'true';
                    editModeAlert.innerHTML = "";
                    if (rects != null) rects.remove();  // удалить вс квадратики по углам полингонов если не в режиме радактирования
                    sendPolyToServer(req);
                    //document.location.reload();	//перезагрузка страницы
                }
                //console.log("editButton.click, editMode=",editMode);
            };

            // статусы полигонов считывать с сервера и обновлять на странице.
            function circleStatusRequest(){
                getStatusFromServer(polygones);
                getStatusHubFromServer();
            };
            // setInterval(circleStatusRequest, 40);
            // setInterval(getTsTableFromServer,1000) // обновляет значение таблицы с количеством проехавших тс

            function notEditModeAlert() {
                editModeAlert.innerHTML = "Добавление, изменение и удаление зон возможно только в режиме редактирования";
                editModeAlert.style.color = '#FF0000'
                //alert("Изменение и удаление зон возможно только в режиме редактирования."); // как альтернатива...
            };
            function winOnmouseUp() { // каждый раз при поднятии мышки данные полигонов сохраняются на сервере.
                if (editMode == 1) {
                    sendPolyToServer(req);
                }
                ;
                if (polygones !== undefined)
                    zeroPolyAlert.innerHTML = "";
                if (polygones.length <=0)
                    zeroPolyAlert.innerHTML = "Данные зон детектирования не заданы";
            };
            window.onmouseup = function () {
                winOnmouseUp();
            };
            function debugInfoShow(event) { // при надажии d показывает статус связи с коммутором
                var kep = event.which;
                //if (event.keyCode == shift && capslock)console.log("shiftCapslock");
                //console.info("Нажата клавиша",kep,"d - дигностика связи");
                if (kep == 68) { // 68 - код клавиши d; 46 -код клавиши del
                    if (hubData.style.visibility == "hidden") hubData.style.visibility = "visible"; else hubData.style.visibility = "hidden";
                    if (polyData.style.visibility == "hidden") polyData.style.visibility = "visible"; else polyData.style.visibility = "hidden";
                }
                ;
            };
            document.body.onkeydown = debugInfoShow;
        }
