module rx
	#(
		parameter 	DBIT = 8 , //databits
						SB_TICK = 16 //ticks for sample bits 
	)
	(
		input wire clk, reset, //boton1,      //
		input wire rx, s_tick,      //rx -> bit entrante, s_tick -> 16 ticks por intervalo, para muestrear un bit
		output reg rx_done_tick,    //se pone en 1 un ciclo despues de que la palabra de 8 bits es recibida
		output wire [DBIT-1:0] dout      //buffer de datos, para leer la palabra recibida
	);
	
	// symbolic state declaration
	localparam [1:0]
		idle = 2'b00,
		start = 2'b01,
		data = 2'b10,
		stop = 2'b11;

	//signal declaration
		reg [1:0] state_reg, state_next; //Estado actual y siguiente de la unidad rx
		reg [3:0] s_reg, s_next;   //cuenta el numero de ticks recibidos
		reg [2:0] n_reg, n_next;	//cuenta el numero de bits de datos recibidos
		reg [DBIT-1:0] b_reg, b_next;	//registro para almacenar los bits recibidos
		
	//body
	//FSMD state & data registers
	always @(posedge clk, posedge reset)//, posedge boton1)
		if (reset)						//resetear la UART receive
			begin
				state_reg <= idle;
				s_reg <= 0;
				n_reg <= 0;
				b_reg <= 8'b10101010;
			end
		//else if (boton1)
		//	begin
		//		state_reg <= start;
		//		s_reg <= 0;
		//		n_reg <= 0;
		//		b_reg <= 8'b1111_0000;
		//	end
		else
			begin
				state_reg <= state_next;
				s_reg <= s_next;
				n_reg <= n_next;
				b_reg <= b_next;
			end
			
	//FSMD next-state logic
	always @*
	begin
		state_next = state_reg; //mantiene el estado de los registros
		rx_done_tick = 1'b0;
		s_next = s_reg;
		n_next = n_reg;
		b_next = b_reg;
		case (state_reg)
			idle:          //antes de comenzar a recibir datos
				if (~rx)		//si rx es 0, bit de start
					begin
						state_next = start;	//siguiente estado: start
						s_next = 0;				//pongo a cero el contador s
					end
			start:							//estado: comienzo de trama
				if (s_tick)						//si llego un tick..
					if (s_reg==7)				//si se alcanzaron los 7 ticks, estamos al medio del bit start
						begin
							state_next = data;	//pasa al siguiente estado: recibir los datos
							s_next = 0;				//pone el contador de ticks a cero
							n_next = 0;				//pone el contador de cant de datos recibidos a cero
						end
					else							//si no, aumenta cantidad de ticks en 1
						s_next = s_reg + 4'b0001;
			data:								//estado: recibiendo datos
				if (s_tick)					//si llego un tick..
					if (s_reg==15)			//si llegamos a los 15 ticks..
						begin
							s_next = 0;		//se reinicia el contador de ticks
							b_next = {rx, b_reg[DBIT-1:1]};		//se almacena el bit recibido
							if (n_reg==(DBIT-1))				//si ya se recibieron todos los bits..
								state_next = stop;				//proximo estado: stop
							else									//si no llegamos a los 8 bits recibidos..
								n_next = n_reg + 3'b001;			//se aumenta la cant de bits recibidos en 1
						end
					else						//si no llegamos a los 15 ticks recibidos
						s_next = s_reg + 4'b0001;	//se aumenta la cant de ticks recib en 1
			stop:							//estado: stop, fin de trama
				if (s_tick)					//si recibimos un tick..
					if (s_reg==(SB_TICK-1))	//si la cantidad de ticks recibidos es 15
						begin
							state_next = idle;	//proximo estado: esperando a recibir nuevo dato
							rx_done_tick = 1'b1;	//dato listo en buffer, para ser leido
						end
					else							//si no..
						s_next = s_reg + 4'b0001;		//aumentamos la cant de ticks recib en 1
		endcase
	end
	
	//output
	assign dout = b_reg;		//asigna registro contenedor de los datos recibidos 
									//al buffer de salida
	
endmodule