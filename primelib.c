#include "primelib.h"
//#include <stdio.h>

//count is counting up to the number of primes that are entered
//i is what is being checked for possibly being prime
 
int primes(int n)
{
   int i = 5, count;
   int *ptr;
   int primes[10000];
   
   if ( n >= 1 )
   {
      primes[0] = 2;
      primes[1] = 3;
   }
 
   for ( count = 3 ; count <= n ;  )
   { 
      
     ptr = primes;
     ptr++;
     while(1)
      {
      
       if ( i%*ptr == 0 )
            break;

       else if((*ptr)*(*ptr) > i)
  {
         if (i < 100000) primes[count-1] = i;
         count++;
         break;
  }
       else
        ptr++;
  
      }


      i+=2;
   }
   //printf("%'d is the %'dth prime\n", i-2, n); // note apostrophes to get commas
   return i-2;
}
