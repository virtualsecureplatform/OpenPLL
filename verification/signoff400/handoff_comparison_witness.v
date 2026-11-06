module proof(input [33:0] a,b);
wire kept_0=({a[13],a[20],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[20],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_0=((a & 34'hfefdfff)==(b & 34'hfefdfff));
wire reproduced_0=kept_0 && omitted_0;
always @* begin assert(reproduced_0==(a==b));assert((!reproduced_0)==(a!=b));end
wire kept_1=({a[13],a[21],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[21],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_1=((a & 34'hfdfdfff)==(b & 34'hfdfdfff));
wire reproduced_1=kept_1 && omitted_1;
always @* begin assert(reproduced_1==(a==b));assert((!reproduced_1)==(a!=b));end
wire kept_2=({a[13],a[22],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[22],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_2=((a & 34'hfbfdfff)==(b & 34'hfbfdfff));
wire reproduced_2=kept_2 && omitted_2;
always @* begin assert(reproduced_2==(a==b));assert((!reproduced_2)==(a!=b));end
wire kept_3=({a[13],a[23],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[23],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_3=((a & 34'hf7fdfff)==(b & 34'hf7fdfff));
wire reproduced_3=kept_3 && omitted_3;
always @* begin assert(reproduced_3==(a==b));assert((!reproduced_3)==(a!=b));end
wire kept_4=({a[13],a[24],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[24],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_4=((a & 34'heffdfff)==(b & 34'heffdfff));
wire reproduced_4=kept_4 && omitted_4;
always @* begin assert(reproduced_4==(a==b));assert((!reproduced_4)==(a!=b));end
wire kept_5=({a[13],a[25],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[25],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_5=((a & 34'hdffdfff)==(b & 34'hdffdfff));
wire reproduced_5=kept_5 && omitted_5;
always @* begin assert(reproduced_5==(a==b));assert((!reproduced_5)==(a!=b));end
wire kept_6=({a[13],a[26],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[26],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_6=((a & 34'hbffdfff)==(b & 34'hbffdfff));
wire reproduced_6=kept_6 && omitted_6;
always @* begin assert(reproduced_6==(a==b));assert((!reproduced_6)==(a!=b));end
wire kept_7=({a[13],a[27],a[28],a[29],a[30],a[31],a[32],a[33]}=={b[13],b[27],b[28],b[29],b[30],b[31],b[32],b[33]});
wire omitted_7=((a & 34'h7ffdfff)==(b & 34'h7ffdfff));
wire reproduced_7=kept_7 && omitted_7;
always @* begin assert(reproduced_7==(a==b));assert((!reproduced_7)==(a!=b));end
endmodule
