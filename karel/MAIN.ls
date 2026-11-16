/PROG  MAIN
/ATTR
OWNER      = MNEDITOR;
COMMENT    = "DESSIN";
PROG_SIZE  = 512;
CREATE     = DATE 26-11-16 TIME 10:00:00;
MODIFIED   = DATE 26-11-16 TIME 10:00:00;
FILE_NAME  = MAIN;
VERSION    = 0;
LINE_COUNT = 22;
MEMORY_SIZE = 512;
PROTECT    = READ_WRITE;
TCD:  STACK_SIZE    = 0,
      TASK_PRIORITY  = 50,
      TIME_SLICE     = 0,
      BUSY_LAMP_ENB  = TRUE,
      ABORT_REQUEST  = TRUE,
      PAUSE_REQUEST  = TRUE,
      DEFAULT_GROUP  = 1,
      AXIS_PRIORITY  = 1, 1, 1, 1, 1, 1;
/MN
   1:  UFRAME_NUM=1 ;
   2:  UTOOL_NUM=1 ;
   3:  ! R[4]=trajectoires restantes, R[5]=deja tracees ;
   4:  R[4]=0 ;
   5:  R[5]=0 ;
   6:  ! Point d approche au-dessus de la zone ;
   7:J PR[9] 50% FINE ;
   8:  LBL[10] ;
   9:  ! Lot suivant : DESSIN.TXT -> PR[74..100], n dans R[3] ;
  10:  CALL RECV_PATH ;
  11:  ! R[3]=0 : dessin termine ;
  12:  IF R[3]=0,JMP LBL[99] ;
  13:  ! Trace du lot (remontees incluses dans les points) ;
  14:  R[2]=73 ;
  15:  FOR R[1]=1 TO R[3] ;
  16:  R[2]=R[2]+1 ;
  17:L PR[R[2]] 100mm/sec CNT100 ;
  18:  ENDFOR ;
  19:  JMP LBL[10] ;
  20:  LBL[99] ;
  21:  ! DESSIN TERMINE ;
  22:J PR[9] 50% FINE ;
/POS
/END
