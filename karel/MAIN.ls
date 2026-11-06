/PROG  MAIN
/ATTR
OWNER      = MNEDITOR;
COMMENT    = "DESSIN";
PROG_SIZE  = 512;
CREATE     = DATE 26-11-06 TIME 10:00:00;
MODIFIED   = DATE 26-11-06 TIME 10:00:00;
FILE_NAME  = MAIN;
VERSION    = 0;
LINE_COUNT = 10;
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
   3:  ! Reception des points (le robot attend le PC) ;
   4:  CALL RECV_PATH ;
   5:  ! n points recus dans PR[10..10+n-1], n dans R[50] ;
   6:  R[2]=9 ;
   7:  FOR R[1]=1 TO R[50] ;
   8:  R[2]=R[2]+1 ;
   9:L PR[R[2]] 100mm/sec CNT100 ;
  10:  ENDFOR ;
  11:  ! DESSIN TERMINE ;
/POS
/END
