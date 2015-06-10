#include <stdio.h>
#include <locale.h>

//count is counting up to the number of primes that are entered
//i is what is being checked for possibly being prime
 
int main(int argc, char *argv[])
{
   int n, i = 5, count;
   int *ptr;
   setlocale(LC_NUMERIC, ""); //to get commas using apostrophe
   printf("What prime are you looking for?\n");
   scanf("%d",&n);
   //int primes[n];
   int primes[10000];
   
   if ( n >= 1 )
   {
      //printf("First %d prime numbers are :\n",n);
      //printf("2\n");
      primes[0] = 2;
      primes[1] = 3;
   }
 
   for ( count = 3 ; count <= n ;  )
   { 
      
     ptr = primes;
     ptr++;
     while(1)
      {
      
       //printf("checking if %d is divisible by %d\n",i,c);
       if ( i%*ptr == 0 )
            break;

       else if((*ptr)*(*ptr) > i)
  {
         if (i < 100000) primes[count-1] = i;
         //printf("%d is prime\n",i);
         count++;
         break;
  }
       else
        ptr++;
  
      }


      i+=2;
   }
   if (argc > 1)
   {
   for(int j = 0; j < n; j++) {
   printf("%d is prime\n", primes[j]);
   }
   }
   else
   printf("%'d is the %'dth prime\n", i-2, n); // note apostrophes to get commas
   return 0;
}
